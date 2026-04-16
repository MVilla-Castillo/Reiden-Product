import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from crm.adapters.dependency_injection import get_use_case

payload = {
    "MessageSid": "SM_TEST_500",
    "WaId": "56965104236",
    "To": "whatsapp:+14155238886",
    "From": "whatsapp:+56965104236",
    "Body": "Hola test crash",
}

try:
    print("Executing UseCase...")
    result = get_use_case().execute(payload)
    print("Success:", result)
except Exception:
    import traceback

    traceback.print_exc()
