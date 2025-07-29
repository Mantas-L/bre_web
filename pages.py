from dataclasses import dataclass, field
from typing import List
from datetime import datetime


@dataclass
class SegmentsPage:
    breadcrumb: str = field(default="")
    searchbar: str = field(default="")
