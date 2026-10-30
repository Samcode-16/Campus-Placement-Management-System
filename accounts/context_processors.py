from django.conf import settings


def legal(request):
    """Makes the privacy / terms details available to every template."""
    return {
        "INSTITUTION_NAME": settings.INSTITUTION_NAME,
        "INSTITUTION_CITY": settings.INSTITUTION_CITY,
        "INSTITUTION_ADDRESS": settings.INSTITUTION_ADDRESS,
        "PRIVACY_CONTACT_EMAIL": settings.PRIVACY_CONTACT_EMAIL,
        "GRIEVANCE_OFFICER": settings.GRIEVANCE_OFFICER,
        "DATA_RETENTION_YEARS": settings.DATA_RETENTION_YEARS,
        "POLICY_VERSION": settings.POLICY_VERSION,
        "POLICY_LAST_UPDATED": settings.POLICY_LAST_UPDATED,
    }
