from typing import Optional

from analyse.k8s.basic import Object


class Rule:

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return self.name == other.name


class Issue:

    def __init__(self, rule: Rule, objects: list[Object] = None, reasons: list[str] = None):
        self.rule = rule
        if objects is None:
            objects = []
        self.objects = objects
        if reasons is None:
            reasons = []
        self.reasons = reasons
        self.case: Optional[str] = None

    def object(self, obj: Object):
        self.objects.append(obj)
        return self

    def reason(self, reason: str):
        self.reasons.append(reason)
        return self

    def case_of(self, case: str):
        self.case = case
        return self

    def __repr__(self):
        return f'Issue({self.rule.name}, case = {self.case}, reasons = {self.reasons}, objects = {self.objects})'

    def to_dict(self):
        return {
            'rule': self.rule.name,
            'case': self.case,
            'reasons': self.reasons,
            'objects': [obj.data for obj in self.objects]
        }
