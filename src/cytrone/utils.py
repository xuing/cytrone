"""
General utility classes and functions for the CyTrONE application.
"""
from string import Template

class MetaAnswerTemplate(Template):
    """
    A custom template for substituting meta answers.
    It allows for more complex variable names that include commas,
    which is used for identifying specific instance variables.
    """
    idpattern = r'[_a-zA-Z,][_a-zA-Z0-9,]*'
