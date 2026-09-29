# Customer Onboarding - Dummy Harness Context

Strategic goal: Enable secure and reliable digital customer acquisition.

Obligation: A customer must complete identity verification, customer creation, account setup and compliance validation before onboarding is complete.

Business process: Customer Onboarding.

The process has the following sequence:
1. Identity Verification
2. Customer Creation
3. Account Creation
4. Compliance Check
5. Welcome Notification

Identity Verification is supported by Identity Service, a microservice. The service exposes POST /identity/verify. In UAT it is available at https://uat.example.com/identity. The API requires a valid customer name, date of birth and identity document number. It is validated by the Identity Verification API Test located at tests/test_identity_verification.py. The automation tag is identity_verification and its execution command is pytest tests/test_identity_verification.py.

Customer Creation is supported by Customer Service, a microservice. The service exposes POST /customers and has a runtime dependency on Identity Service. In UAT it is available at https://uat.example.com/customers. The API requires a verified identity reference, unique email and valid address. It is validated by the Customer Creation API Test located at tests/test_customer_creation.py. The automation tag is customer_creation and its execution command is pytest tests/test_customer_creation.py.

Account Creation is supported by Account Service, a microservice. The service exposes POST /accounts and has a runtime dependency on Customer Service. In UAT it is available at https://uat.example.com/accounts. The API requires an existing customerId, account type and currency. It is validated by the Account Creation API Test located at tests/test_account_creation.py. The automation tag is account_creation and its execution command is pytest tests/test_account_creation.py.

Compliance Check is supported by Compliance Service, a microservice. The service exposes POST /compliance/check and has runtime dependencies on Customer Service and Account Service. In UAT it is available at https://uat.example.com/compliance. The API requires customerId, accountId, customer country and KYC status. It is validated by the Compliance Check API Test located at tests/test_compliance_check.py. The automation tag is compliance_check and its execution command is pytest tests/test_compliance_check.py.

Welcome Notification is supported by Notification Service, a microservice. The service exposes POST /notifications/welcome and has a runtime dependency on Compliance Service. In UAT it is available at https://uat.example.com/notifications. The API requires customerId, email or mobile number and notification preference. It is validated by the Welcome Notification API Test located at tests/test_welcome_notification.py. The automation tag is welcome_notification and its execution command is pytest tests/test_welcome_notification.py.
