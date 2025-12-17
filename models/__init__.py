from sqlalchemy.orm import declarative_base

Base = declarative_base()

# --------------------------------------------------
# Core commerce / orders
# --------------------------------------------------
from .packages import Package  # noqa: F401
from .licenses import License  # noqa: F401
from .orders import Order  # noqa: F401
from .order_billing_details import OrderBillingDetails  # noqa: F401

# --------------------------------------------------
# Partners & payouts
# --------------------------------------------------
from .partners import Partner  # noqa: F401
from .partner_payouts import PartnerPayout  # noqa: F401
from .partner_payments import PartnerPayment  # noqa: F401

# --------------------------------------------------
# Partner onboarding / requests
# --------------------------------------------------
from .partner_requests import PartnerRequest  # noqa: F401
from .trial_requests import TrialRequest  # noqa: F401

# --------------------------------------------------
# Admin
# --------------------------------------------------
from .admin import Admin  # noqa: F401
