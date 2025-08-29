# AWS Elastic Beanstalk Deployment Guide for Agent-3.0 Treasury Manager

## Overview
This guide documents the complete deployment process for Agent-3.0 Treasury Manager AI Agent to AWS Elastic Beanstalk. The application is a Flask-based API that processes Excel files and generates payment proposals using AI crews.

## Prerequisites

### 1. AWS Credentials
- AWS Access Key ID and Secret Access Key with Elastic Beanstalk permissions
- Configured in `.env` file:
  ```
  AWS_ACCESS_KEY_ID=your_access_key
  AWS_SECRET_ACCESS_KEY=your_secret_key
  AWS_REGION_NAME=us-east-1
  ```

### 2. Required Tools
- Python 3.11+
- pip package manager
- curl for testing

## Application Structure
```
Agent-3.0/
├── application.py          # Main Flask app (EB compatible)
├── flask_server.py         # Original Flask app (kept for reference)
├── requirements.txt        # Python dependencies
├── crew.py                # AI crew orchestration
├── tools/                 # Treasury tools
├── src/                   # Source code
├── .env                   # Environment variables
├── .ebignore              # EB deployment exclusions
└── test files/            # Test data
```

## Step 1: Install EB CLI

```bash
pip install awsebcli
```

Verify installation:
```bash
eb --version
```

## Step 2: Application Modifications for Elastic Beanstalk

### 2.1 Create EB-Compatible Main File
EB requires the main Flask file to be named `application.py` with Flask instance named `application`:

```bash
cp flask_server.py application.py
```

### 2.2 Modify Flask Instance Names
In `application.py`, change:
- `app = Flask(__name__)` → `application = Flask(__name__)`
- All `@app.route` → `@application.route`
- `app.run()` → `application.run()`

### 2.3 Add Root Route for Health Checks
EB load balancer checks root path `/`, so add this route:

```python
@application.route('/', methods=['GET'])
def root():
    """Root endpoint for health checks."""
    return jsonify({"status": "healthy", "service": "Treasury Manager AI Agent"})
```

### 2.4 Fix Web3 Import Issues
Update `tools/treasury_usdt_payment_tool.py`:
```python
# Change this:
from web3.exceptions import ValidationError

# To this:
from web3.exceptions import Web3ValidationError
```

## Step 3: Create Deployment Configuration Files

### 3.1 Create .ebignore
```bash
cat > .ebignore << 'EOF'
# Virtual environments
virt/
venv/
env/
.venv/

# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd
.Python

# IDE files
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db

# Git
.git/
.gitignore

# Test files
tests/
test_data/

# Development files
.env
flask_server.py

# Temporary files
tmp/
*.log
EOF
```

### 3.2 Verify requirements.txt
Ensure it contains all necessary dependencies:
```
Flask>=3.0
gunicorn>=21.2
python-dotenv>=1.0
crewai>=0.40
pydantic>=1.10
web3>=6.0
pandas>=2.1
openpyxl>=3.1
boto3>=1.28
```

## Step 4: Initialize and Deploy to Elastic Beanstalk

### 4.1 Set AWS Environment Variables
```bash
export AWS_ACCESS_KEY_ID=your_access_key_id
export AWS_SECRET_ACCESS_KEY=your_secret_access_key
export AWS_DEFAULT_REGION=us-east-1
```

### 4.2 Initialize EB Application
```bash
eb init -p python-3.11 treasury-agent --region us-east-1
```

### 4.3 Create and Deploy Environment
```bash
eb create treasury-env --instance-type t3.micro
```

### 4.4 Configure Environment Variables
```bash
eb setenv \
  MODEL=bedrock/us.amazon.nova-pro-v1:0 \
  RISK_ASSESSOR_MODEL=bedrock/us.amazon.nova-pro-v1:0 \
  PROPOSAL_PROCESSOR_MODEL=bedrock/us.amazon.nova-pro-v1:0 \
  PAYMENT_SPECIALIST_MODEL=bedrock/us.amazon.nova-pro-v1:0 \
  AWS_ACCESS_KEY_ID=your_access_key_id \
  AWS_SECRET_ACCESS_KEY=your_secret_access_key \
  AWS_REGION_NAME=us-east-1
```

## Step 5: Post-Deployment Updates

### 5.1 Deploy Code Changes
```bash
eb deploy
```

### 5.2 Check Application Status
```bash
eb status
eb health
```

### 5.3 View Logs
```bash
eb logs
eb logs --all  # Download all logs locally
```

## Step 6: Testing the Deployed API

### 6.1 Test Health Endpoints
```bash
# Root endpoint (for EB health checks)
curl http://your-app-url.elasticbeanstalk.com/

# Health endpoint
curl http://your-app-url.elasticbeanstalk.com/health
```

### 6.2 Test Complete API Workflow

**Step 1: Submit Request**
```bash
curl -X POST \
  -F "excel=@dummy_financial_data.xlsx" \
  -F 'json={"user_id":"test_user_001","risk_config":{"min_balance_usd":2000.00,"transaction_limits":{"single":25000.00,"daily":50000.00}},"user_notes":"Test payment processing"}' \
  http://your-app-url.elasticbeanstalk.com/submit_request
```

**Step 2: Get Payment Proposal**
```bash
curl http://your-app-url.elasticbeanstalk.com/get_payment_proposal/{proposal_id}
```

**Step 3: Submit Payment Approval**
```bash
curl -X POST \
  -H "Content-Type: application/json" \
  -d '{"proposal_id":"your-proposal-id","custody_wallet":"0x742d35Cc6634C0532925a3b8D4C9db96C4b4d8b6","private_key":"test_key","approval_decision":"approve_all","comments":"Approved"}' \
  http://your-app-url.elasticbeanstalk.com/submit_payment_approval
```

**Step 4: Get Execution Result**
```bash
curl http://your-app-url.elasticbeanstalk.com/payment_execution_result/{proposal_id}
```

## Troubleshooting

### Common Issues and Solutions

#### 1. HTTP 4xx Health Check Failures
**Problem**: EB health checks return 404 errors
**Solution**: Ensure root route `/` exists and returns 200 status

#### 2. Import Errors
**Problem**: `ValidationError` import fails from web3.exceptions
**Solution**: Use `Web3ValidationError` instead

#### 3. Missing Environment Variables
**Problem**: Crew agents fail due to missing model environment variables
**Solution**: Set all required environment variables using `eb setenv`

#### 4. Connection Timeout on HTTPS
**Problem**: curl hangs on HTTPS requests
**Solution**: Use HTTP instead (EB doesn't configure SSL by default)

#### 5. Deployment Fails
**Problem**: Application deployment fails
**Solution**: Check logs with `eb logs` and verify all dependencies are in requirements.txt

### Viewing Detailed Logs
```bash
# Real-time logs
eb logs --all

# Specific log files (after downloading)
cat .elasticbeanstalk/logs/latest/i-*/var/log/web.stdout.log
cat .elasticbeanstalk/logs/latest/i-*/var/log/nginx/access.log
cat .elasticbeanstalk/logs/latest/i-*/var/log/nginx/error.log
```

## Environment Management

### Update Environment Variables
```bash
eb setenv KEY=VALUE KEY2=VALUE2
```

### Scaling
```bash
eb scale 2  # Scale to 2 instances
```

### Terminate Environment
```bash
eb terminate treasury-env
```

## Security Notes

1. **Never commit AWS credentials** to version control
2. **Use IAM roles** for production deployments instead of access keys
3. **Enable HTTPS** for production by configuring SSL certificate
4. **Restrict security groups** to necessary ports and IP ranges
5. **Use encrypted environment variables** for sensitive data

## Production Considerations

### 1. Instance Type
- Development: `t3.micro` (free tier eligible)
- Production: `t3.small` or larger based on load

### 2. Load Balancer
- Configure health check path to `/health`
- Set appropriate timeout values
- Enable sticky sessions if needed

### 3. Database
- Configure RDS for persistent data storage
- Update connection strings in environment variables

### 4. Monitoring
- Enable CloudWatch monitoring
- Set up alerts for application errors
- Configure log retention policies

## Final Deployment URLs

- **Application**: http://treasury-env.eba-9kpff4ph.us-east-1.elasticbeanstalk.com
- **Health Check**: http://treasury-env.eba-9kpff4ph.us-east-1.elasticbeanstalk.com/health
- **API Documentation**: See `api_documentation.md` in project root

## Success Criteria

✅ All API endpoints return successful responses
✅ Health checks pass (Green status in EB console)  
✅ Complete workflow test passes (submit → proposal → approval → result)
✅ No 4xx/5xx errors in logs
✅ Environment variables properly configured
✅ Flask application runs without import errors

---

**Last Updated**: 2025-08-29
**Deployment Environment**: treasury-env.eba-9kpff4ph.us-east-1.elasticbeanstalk.com
**Status**: ✅ Successfully Deployed and Tested
