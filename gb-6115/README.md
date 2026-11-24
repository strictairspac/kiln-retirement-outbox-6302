# 砖枫热作·烘箱退役证书交卷

一起登记炉体退役和证书待交卷事件，回放值守断联与租约补领，并检查归档副作用只发生一次。

## 业务流程

1. 退役交接台
2. 炉体退役批次
3. 外盒回放
4. 证书回执

PostgreSQL 事务外盒、租约确认代次、唯一键收据和故障后重领。

设备组以前在台账标记退役，再用人工清单抄给档案室，容易写上退役却遗漏证书、中断后重复投递、值守结束时说不清谁已接收。上游是炉体封板退役登记，下游是档案当班员和设备主管。

16:00 打开 ovens-retirement-1124.json 对应的封板批次。16:04 检查 OV-217 的退役异常。16:08 设归档领取租期 12 秒。16:10 执行回放。16:14 核对 OV-217 未写入退役证书。16:16 核对 OV-203 领取两次但只保留一张收据。16:20 以短值守窗口生成待补领交接单。

退役变更与待投递事件同在数据库保存点中，事件前失败回滚整项。领取用 FOR UPDATE SKIP LOCKED 原子加租约，收据按证书幂等键唯一，确认须匹配租约代次和时限。模拟收据后断联会保留收据但不确认，租约到期才再次领取。

场景在单个 PostgreSQL 运行事务和隔离临时表中回放，多个逻辑步骤用保存点表示，不启动外部收件系统，也不模拟整个运行进程崩溃。幂等保证针对演练中的数据库收据键。

## 启动

```sh
cp -n .env.example .env
docker compose config --quiet
docker compose up -d --build --wait
```

打开 <http://localhost:18316>。OpenAPI 在 <http://localhost:19316/docs>，数据库映射到本机 17816。所有暴露端口只绑定回环地址。Compose 启动 frontend、backend、worker、db、redis，各自通过健康探针检查。数据库、Redis 和共享产物目录各有命名卷；任务状态及导出内容以数据库中的证据为准。

首次启动时幂等载入演示数据。手动载入可运行 `docker compose exec -T backend python -m scripts.seed_demo`。常规停止可用 `docker compose down`。验收环境清理才加 `-v`，它会删除本项目的数据卷。

## 角色与交接

演示账号共用口令 `Demo-DbWorkbench-2026`。

| 登录名 | 角色 | 可执行操作 |
|---|---|---|
| operator | 资料操作员 | 登记业务资料、设置「归档领取租期（秒）」、提交、查看和下载结果 |
| reviewer | 业务复核员 | 查看执行证据、签署单次复核、下载交接单 |
| viewer | 只读观察员 | 查看资料、执行结果及审计，下载证据 |

选用「ovens-retirement-1124.json」对应的演示资料，保存一份复演资料，再以默认参数 12 提交。worker 保存结果摘要、业务明细和 SHA-256。复核员登录后在「证书回执」签署。

## 开发说明

| 部分 | 实现 |
|---|---|
| 前端 | 原生 HTML、CSS、JavaScript ES Modules、Nginx |
| 后端 | Python 3.11、FastAPI、SQLAlchemy、JWT |
| 数据库 | PostgreSQL 16 |
| 后台执行 | Redis 通知、数据库持久任务队列和行锁、Python worker |

从 `backend/src/domain/scenario.py` 修改业务入口和演示口径，运行 `docker compose up -d --build --wait` 查看变更。数据库表结构在 `backend/src/models` 和 `backend/migrations`，输入模型在 `backend/src/schemas`。业务页和请求接口在 `frontend/src/pages`、`frontend/src/api`。资料、执行、复核三个工作流实体各有独立表和 API；场景输入及结果保留在所属资料和批次中。

角色枚举在 `backend/src/constants/roles.py`、`frontend/src/constants/roles.js`，用于服务端访问控制、账号初始化、前端导航与签署。批次状态在 `backend/src/constants/job_state.py`、`frontend/src/constants/states.js`，用于队列、状态 API、状态标记与轮询。登记、提交、完成和签署事件写入审计表。

`COMPOSE_PROJECT_NAME` 设置栈名，`FRONTEND_PORT`、`BACKEND_PORT`、`DB_PORT` 设置端口。通过 `DB_PASSWORD`、`JWT_SECRET`、`DEMO_PASSWORD` 配置本地凭据。设置 `SEED_DEMO=false` 可关闭演示数据载入，此时数据库初始没有演示账号。数据库密码调整后，已有数据卷需在数据库内同步修改用户密码。

## 验收范围

领取时间与中断由场景重放。领取、签收与去重使用真实 PostgreSQL 事务与约束，收据留存在模拟档案表。 当前界面用 JSON 编辑业务资料，以 JSON 下载证据。过程和截图保存在批次的 [验收记录](../../test-artifacts/gb-6115/TESTING.md)。

[MIT License](LICENSE)
