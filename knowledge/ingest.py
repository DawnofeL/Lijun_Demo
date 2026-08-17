"""文件切分入库。

按标题层级切段，不按固定字数硬切。规范类文件的一条条款就是一个语义单元，
硬切会把条款劈成两半，检索出来的片段就没法当作出处使用。

资料量小，索引放在记忆体，不需要向量资料库。
"""

import re
from dataclasses import dataclass, field

import config

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


@dataclass
class Chunk:
    id: int
    source: str                  # 档案名
    heading_path: list[str]      # 标题路径，例：["一、住客跌倒的處理流程", "1.2 通報時限"]
    text: str
    line_start: int
    line_end: int
    tokens: set = field(default_factory=set)

    @property
    def citation(self) -> str:
        # 首层标题就是文件标题，来源名已经带了，不重复显示
        path = [h for h in self.heading_path[1:] if h]
        return f"{self.source} · {' › '.join(path)}" if path else self.source

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "heading_path": self.heading_path,
            "citation": self.citation,
            "text": self.text,
            "lines": [self.line_start, self.line_end],
        }


_INDEX: list[Chunk] = []


def tokenize(text: str) -> set:
    """中文按二元切分，英数按单词切分。

    规范问答的查询词和原文用词高度重合，二元切分足够，
    不引入分词套件可以少一个相依，也少一处版本风险。
    """
    tokens = set()
    for word in re.findall(r"[A-Za-z0-9]+", text.lower()):
        tokens.add(word)
    chinese = re.sub(r"[^\u4e00-\u9fff]", "", text)
    for i in range(len(chinese)):
        tokens.add(chinese[i])
        if i + 1 < len(chinese):
            tokens.add(chinese[i:i + 2])
    return tokens


def _flush(buffer: list[str], heading_path: list[str], source: str,
           line_start: int, line_end: int, chunks: list[Chunk]) -> None:
    body = "\n".join(buffer).strip()
    if not body:
        return
    chunk = Chunk(
        id=len(chunks) + 1,
        source=source,
        heading_path=list(heading_path),
        text=body,
        line_start=line_start,
        line_end=line_end,
    )
    chunk.tokens = tokenize(" ".join(heading_path) + " " + body)
    chunks.append(chunk)


def load_corpus() -> int:
    """读取 corpus 目录下全部文件，切段建索引。回传段落数。"""
    _INDEX.clear()
    if not config.CORPUS_DIR.exists():
        return 0

    for path in sorted(config.CORPUS_DIR.glob("*.md")) + sorted(config.CORPUS_DIR.glob("*.txt")):
        source = path.stem
        lines = path.read_text(encoding="utf-8").splitlines()
        heading_path: list[str] = []
        buffer: list[str] = []
        start = 1

        for number, line in enumerate(lines, start=1):
            match = HEADING.match(line)
            if not match:
                buffer.append(line)
                continue

            _flush(buffer, heading_path, source, start, number - 1, _INDEX)
            buffer = []
            start = number

            level = len(match.group(1))
            title = match.group(2).strip()
            heading_path = heading_path[:level - 1]
            while len(heading_path) < level - 1:
                heading_path.append("")
            heading_path.append(title)

        _flush(buffer, heading_path, source, start, len(lines), _INDEX)

    return len(_INDEX)


def index() -> list[Chunk]:
    return _INDEX


def stats() -> dict:
    sources = sorted({chunk.source for chunk in _INDEX})
    return {"chunks": len(_INDEX), "sources": sources}
