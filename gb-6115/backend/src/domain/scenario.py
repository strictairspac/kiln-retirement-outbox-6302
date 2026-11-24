from .delivery import replay
from .fixtures import FIXTURES
from .inputs import parse
from .workshop import RetirementTables


CONFIG = {
    "title": "砖枫热作·烘箱退役证书交卷",
    "team": "砖枫热作 10 人设备退役及档案室",
    "description": "一起登记炉体退役和证书待交卷事件，回放值守断联与租约补领，并检查归档副作用只发生一次。",
    "direction": "事务外盒与幂等交付",
    "mechanism": "PostgreSQL 事务外盒、租约确认代次、唯一键收据和故障后重领。",
    "modules": ["退役交接台", "炉体退役批次", "外盒回放", "证书回执"],
    "unit": "退役卷",
    "max_parameter": 300,
    "default_parameter": 12,
    "parameter_label": "归档领取租期（秒）",
    "facts": ["原子登记", "租约续领", "幂等收据"],
    "palette": 15,
    "fixture": "ovens-retirement-1124.json",
}


def validate(payload):
    parse(payload)


def run(payload, parameter, db):
    requests, until = parse(payload)
    tables = RetirementTables(db)
    tables.create(requests)
    for request in requests:
        tables.retire(request)
    suppressed = replay(tables, until, parameter)
    rows = []
    delivered = pending = rolled_back = receipts = 0
    for row in tables.result_rows():
        rolled_back += row["certificate"] is None
        delivered += row["acknowledged"] is True
        pending += row["acknowledged"] is False
        receipts += row["archived_at"] is not None
        state = "退役已撤销"
        if row["certificate"] is not None:
            state = "已确认" if row["acknowledged"] else "租约待补领"
        rows.append({
            "炉体": row["asset"],
            "退役证书": row["certificate"],
            "领取次数": row["attempts"] or 0,
            "收据时间 s": row["archived_at"],
            "交卷状态": state,
        })
    return {
        "summary": f"已确认 {delivered} 张，待补领 {pending} 张，撤销 {rolled_back} 条退役；唯一约束抑制 {suppressed} 次重复归档。",
        "metrics": {"确认交卷": delivered, "待补领": pending, "退役撤销": rolled_back, "收据行": receipts, "拦截重复": suppressed},
        "rows": rows,
    }
