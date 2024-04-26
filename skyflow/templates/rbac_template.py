"""Role template."""
import enum
from typing import List

from pydantic import BaseModel, Field, field_validator

from skyflow.templates.object_template import ObjectList, ObjectMeta
from skyflow.templates.templates_exception import RBACTemplateException, RuleException


VALID_OBJECT_CLASSES = [
    'jobs',
    'filterpolicies',
    'services',
    'endpoints',
    'clusters',
    'namespaces',
    'links',
    'roles',
    'rolebindings',
    'user',
]


class ActionEnum(enum.Enum):
    """Types of actions performed on Skyflow objects."""
    CREATE = "create"
    GET = "get"
    LIST = "list"
    UPDATE = "update"
    PATCH = "patch"
    DELETE = "delete"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)


class Rule(BaseModel):
    """Specifies the rules of a role."""
    name: str = Field(default="", validate_default=True)
    resources: List[str] = Field(default=[], validate_default=True)
    actions: List[str] = Field(default=[], validate_default=True)

    @field_validator('resources')
    @classmethod
    def validate_resources(cls, resources: List[str]) -> List[str]:
        """
        Validates the resources field.
        """
        if "*" in resources:
            if len(resources) != 1:
                raise RuleException(f"Invalid resources: {resources}")
            return resources
        for res in resources:
            if res not in VALID_OBJECT_CLASSES:
                raise RuleException(f"Invalid resources: {resources}")
        return resources

    @field_validator('actions')
    @classmethod
    def validate_actions(cls, actions: List[str]) -> List[str]:
        """
        Validates the rules field.
        """
        possible_actions = [a.value for a in ActionEnum]
        if "*" in actions:
            if len(actions) != 1:
                raise RuleException(f"Invalid actions: {actions}")
            return actions
        for act in actions:
            if act not in possible_actions:
                raise RuleException(f"Invalid actions: {actions}")
        return actions


class RoleMeta(ObjectMeta):
    """Metadata of a job."""
    namespaces: List[str] = Field(default=[], validate_default=True)


class Role(BaseModel):
    """Specifies the role of a user."""
    kind: str = Field(default="Role")
    metadata: RoleMeta = Field(default=RoleMeta())
    rules: List[Rule]
    users: List[str] = Field(default=[], validate_default=True)

    def get_name(self):
        """Returns the name of an object."""
        return self.metadata.name  # pylint: disable=no-member


class RoleList(ObjectList):
    """List of role objects."""
    kind: str = Field(default="RoleList")
