"""
Utility functions for Plugins.
"""
from typing import Dict, Optional, Tuple
from skyflow.templates import LabelSelectorOperatorEnum, MatchExpression


def match_labels_satisfied(labels_subset: Dict[str, str],
                           labels_superset: Dict[str, str]) -> bool:
    return all(k in labels_superset and labels_superset[k] == v
               for k, v in labels_subset.items())


def match_expressions_satisfied(
        source_expression: MatchExpression,
        labels_superset: Dict[str, str]) -> Tuple[bool, Optional[str]]:
    """
    Determines expression criteria against labels superset.  Expression
    criteria is based on the expression operator.  For example the 
    operator can be defined as 'In' or 'NotIn'.  Determining
    if the expression is satisfied is dependent of the operator.
    """
    # Check for expression key existance and handle base on operator
    key_found_in_superset = source_expression.key in labels_superset
    if not key_found_in_superset:
        # 'In' Operator
        if source_expression.operator == LabelSelectorOperatorEnum.IN.value:
            return False, f"Label key '{source_expression.key}' not found in cluster labels"
        elif source_expression.operator == LabelSelectorOperatorEnum.NOTIN.value:
            return True, None
        # Unknown
        else:
            return False, f'Unknown operator'

    # Check for superset value existance in expression values
    # and handle base on operator
    superset_value = labels_superset[source_expression.key]
    value_found = superset_value in source_expression.values
    if value_found:
        # 'In' Operator
        if source_expression.operator == LabelSelectorOperatorEnum.IN.value:
            return True, None
        # 'NotIn' Operator"
        elif source_expression.operator == LabelSelectorOperatorEnum.NOTIN.value:
            return False, f"Label value '{superset_value}' found in cluster labels"
    else:
        # 'In' Operator
        if source_expression.operator == LabelSelectorOperatorEnum.IN.value:
            return False, f'Label values not found in cluster labels'
        # 'NotIn' Operator"
        elif source_expression.operator == LabelSelectorOperatorEnum.NOTIN.value:
            return True, None
    # Unknown
    return False, f'Unknown operator'
