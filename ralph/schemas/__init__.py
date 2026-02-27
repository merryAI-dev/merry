"""Document-type specific Pydantic schemas for extraction validation."""

from .base import ExtractionResult
from .business_reg import BusinessRegistration
from .financial_stmt import FinancialStatementSet
from .shareholder import ShareholderRegistry
from .investment_review import InvestmentReview
from .employee_list import EmployeeList
from .certificate import CertificateSet
from .startup_cert import StartupCertificate
from .articles import Articles

# Document type → Schema class mapping
SCHEMA_MAP: dict[str, type[ExtractionResult]] = {
    "business_reg": BusinessRegistration,
    "financial_stmt": FinancialStatementSet,
    "shareholder": ShareholderRegistry,
    "investment_review": InvestmentReview,
    "employee_list": EmployeeList,
    "certificate": CertificateSet,
    "startup_cert": StartupCertificate,
    "articles": Articles,
}

__all__ = [
    "ExtractionResult",
    "BusinessRegistration",
    "FinancialStatementSet",
    "ShareholderRegistry",
    "InvestmentReview",
    "EmployeeList",
    "CertificateSet",
    "StartupCertificate",
    "Articles",
    "SCHEMA_MAP",
]
