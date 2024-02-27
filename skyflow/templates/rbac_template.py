import enum

from pydantic import BaseModel, Field, field_validator
from typing import List

from skyflow.templates.object_template import ObjectMeta, ObjectList

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
]

class ActionEnum(enum.Enum):
    """Types of actions performed on Skyflow objects."""
    CREATE = "create"
    GET = "get"
    UPDATE = "update"
    PATCH = "patch"
    DELETE = "delete"

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value == other
        return super().__eq__(other)

class Rule(BaseModel):
    name: str  = Field(default="",
                        validate_default=True)
    resources: List[str] = Field(default=[],
                                 validate_default=True)
    actions: List[str] = Field(default=[],
                               validate_default=True)
    
    @field_validator('resources')
    @classmethod
    def validate_resources(cls, resources: str) -> str:
        """
        Validates the resources field.
        """
        print(resources)
        if "*" in resources:
            if len(resources) !=1:
                raise ValueError(f"Invalid resources: {resources}")
            else:
                return resources
        for r in resources:
            if r not in VALID_OBJECT_CLASSES:
                raise ValueError(f"Invalid resources: {resources}")
        return resources

    @field_validator('actions')
    @classmethod
    def validate_rules(cls, rules: List[str]) -> str:
        """
        Validates the rules field.
        """
        possible_actions = [a.value for a in ActionEnum]
        if "*" in rules:
            if len(rules) != 1:
                raise ValueError(f"Invalid actions: {rules}")
            else:
                return rules
        for r in rules:
            if r not in possible_actions:
                raise ValueError(f"Invalid actions: {rules}")
        return rules

class RoleMeta(ObjectMeta):
    """Metadata of a job."""
    namespaces: List[str] = Field(default=[],
                                  validate_default=True)

class Role(BaseModel):
    kind: str = Field(default="Role")
    metadata: RoleMeta = Field(default=RoleMeta())
    rules: List[Rule]
    users: List[str] = Field(default=[],
                             validate_default=True)

    def get_name(self):
        """Returns the name of an object."""
        return self.metadata.name  # pylint: disable=no-member


class RoleList(ObjectList):
    """List of role objects."""
    kind: str = Field(default="RoleList")

if __name__ == '__main__':
    Role()
