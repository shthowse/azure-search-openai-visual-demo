from abc import ABC
from typing import Any, AsyncGenerator, Optional, Union
from dataclasses import dataclass

from core.authentication import AuthenticationHelper


@dataclass
class ThoughtStep:
    title: str
    description: Any | str | None
    props: Optional[dict[str, Any]] = None


class Approach:
    def build_filter(self, overrides: dict[str, Any], auth_claims: dict[str, Any]) -> Optional[str]:
        exclude_category = overrides.get("exclude_category") or None
        security_filter = AuthenticationHelper.build_security_filters(overrides, auth_claims)
        filters = []
        if exclude_category:
            filters.append("category ne '{}'".format(exclude_category.replace("'", "''")))
        if security_filter:
            filters.append(security_filter)
        return None if len(filters) == 0 else " and ".join(filters)

    async def run(
        self, messages: list[dict], stream: bool = False, session_state: Any = None, context: dict[str, Any] = {}
    ) -> Union[dict[str, Any], AsyncGenerator[dict[str, Any], None]]:
        raise NotImplementedError
