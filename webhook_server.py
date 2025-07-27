# webhook_server.py
from flask import Flask, request, jsonify
import json, hmac, hashlib

app = Flask(__name__)

STRIPE_WEBHOOK_SECRET = "whsec_..."  # Replace with your real Stripe webhook secret
USERS_FILE = "users.json"

def update_subscription(email):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    if email in users:
        users[email]["subscribed"] = True
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=4)

@app.route("/webhook", methods=["POST"])
def stripe_webhook():
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature")
    event = None

    try:
        import stripe
        stripe.api_key = "sk_test_..."  # Your secret key
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("Webhook error:", str(e))
        return jsonify(success=False), 400

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session["customer_details"]["email"]
        print("✅ Payment success for:", customer_email)
        update_subscription(customer_email)

    return jsonify(success=True)

if __name__ == "__main__":
    app.run(port=4242)
