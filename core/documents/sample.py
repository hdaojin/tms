from datetime import date
from functools import lru_cache
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont

from .types import DocumentAsset, DocumentInput

_SAMPLE_INTRO = """## 训练概况

本次训练涵盖网络连通性、路由收敛和故障排查。完成后保留验证结果与复盘记录。

- 核对网关、路由和访问策略。
- 使用分层排查方法验证客户端到服务端的连通性。
- 根据记录复盘每个检查项。

> 变更前先记录设备状态，变更后复查关键路径。

![网络训练拓扑](tms-asset:topology)

## 验证命令

```sh
ping -c 4 192.0.2.20
ip route get 192.0.2.20
printf '%s\\n' 'check <latency> & packet loss'
```

## 检查记录

| 序号 | 检查项 | 验证结果 |
| --- | --- | --- |
"""
_SAMPLE_ROWS = "\n".join(
    f"| {index:02} | {item} | 已验证，记录响应时间和结果。 |"
    for index, item in enumerate(("网关连通性", "路由可达性", "服务访问策略") * 18, 1)
)


@lru_cache(maxsize=1)
def topology_asset() -> DocumentAsset:
    image = Image.new("RGB", (840, 200), "#eef3f8")
    draw = ImageDraw.Draw(image)
    draw.line((125, 100, 715, 100), fill="#24568a", width=4)
    font = ImageFont.load_default(size=23)
    for x, label in ((35, "Client"), (330, "Gateway"), (625, "Server")):
        draw.rounded_rectangle((x, 60, x + 180, 140), radius=10, fill="#204469")
        draw.text((x + 90, 100), label, fill="#ffffff", font=font, anchor="mm")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return DocumentAsset(buffer.getvalue(), "image/png")


def sample_document(template_id="standard") -> DocumentInput:
    return DocumentInput(
        title="网络系统管理训练报告",
        subtitle="连通性验证与故障排查",
        author="训练教练组",
        organization="网络系统管理项目组",
        document_date=date(2026, 11, 12),
        content=_SAMPLE_INTRO + _SAMPLE_ROWS + "\n\n## 复盘结论\n\n完成全部检查项。\n",
        template_id=template_id,
        assets={"topology": topology_asset()},
    )
