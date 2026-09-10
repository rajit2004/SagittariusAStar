
from api.sms import SMSSettings

def test_sms_settings_phone_validation():

    valid_settings = SMSSettings(phoneNumber="+919876543210", enabled=False)
    assert valid_settings.normalized_phone == "+919876543210"

    empty_settings = SMSSettings(phoneNumber="", enabled=False)
    assert empty_settings.normalized_phone is None

    invalid_settings = SMSSettings(phoneNumber="invalid_12345", enabled=False)
    assert invalid_settings.normalized_phone == "invalid_12345"
