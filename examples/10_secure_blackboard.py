"""
HiveFlow - 10: Secure Blackboard

This example demonstrates encrypted blackboard with audit logging.

Usage:
    pip install "hiveflow[security]"
    python 10_secure_blackboard.py
"""
import asyncio
import os
from cryptography.fernet import Fernet
from hiveflow import HiveFlow, HiveFlowConfig, EnvKeyProvider


async def main():
    print("=== Secure Blackboard Example ===\n")

    os.environ.setdefault("HIVEFLOW_ENCRYPTION_KEY", Fernet.generate_key().decode())

    config = HiveFlowConfig(
        blackboard_type="encrypted",
        encryption_key_provider=EnvKeyProvider("HIVEFLOW_ENCRYPTION_KEY"),
    )
    hf = HiveFlow(config)
    await hf.start()

    try:
        print("Writing sensitive data...")
        await hf.blackboard.sys_put("api_credentials", {
            "api_key": "sk-secret-123",
            "endpoint": "https://api.example.com",
        })
        await hf.blackboard.sys_put("user_data", {
            "user_id": "user123",
            "email": "user@example.com",
        })

        creds = await hf.blackboard.sys_get("api_credentials")
        user = await hf.blackboard.sys_get("user_data")
        print(f"  Retrieved credentials: endpoint={creds['endpoint']}")
        print(f"  Retrieved user: {user['email']}")

        print("\nSecureBlackboard wraps storage with audit logging and access control.")
        print("Use blackboard_type='encrypted' for AES encryption at rest.")

    finally:
        await hf.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
