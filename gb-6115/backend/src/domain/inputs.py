import re
from dataclasses import dataclass

ASSET_CODE = re.compile(r"[A-Z0-9][A-Z0-9-]{0,23}")
STAGES = ("none", "before_enqueue", "after_receipt")


@dataclass(frozen=True)
class Request:
    asset: str
    certificate: str
    failed_stage: str


def parse(payload):
    if not isinstance(payload, dict):
        raise ValueError("请输入退役批次")
    until = payload.get("observe_until")
    if type(until) is not int or not 0 <= until <= 300:
        raise ValueError("观察时限为 0 到 300 秒")
    records = payload.get("requests")
    if not isinstance(records, list) or not 1 <= len(records) <= 120:
        raise ValueError("每批 1 到 120 台烘箱")
    requests = []
    for item in records:
        if not isinstance(item, dict) or set(item) != {"asset", "certificate", "failed_stage"}:
            raise ValueError("退役项需要 asset、certificate、failed_stage 字段")
        request = Request(**item)
        if any(not isinstance(code, str) or not ASSET_CODE.fullmatch(code) for code in (request.asset, request.certificate)):
            raise ValueError("炉号和证书号只允许大写字母、数字及连字符")
        if request.failed_stage not in STAGES:
            raise ValueError("失败阶段只支持 none、before_enqueue、after_receipt")
        requests.append(request)
    if len({item.asset for item in requests}) != len(requests):
        raise ValueError("同炉号不能重复提交")
    if len({item.certificate for item in requests}) != len(requests):
        raise ValueError("同证书号不能重复使用")
    return requests, until
