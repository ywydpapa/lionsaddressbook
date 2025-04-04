from passlib.context import CryptContext

# Create a CryptContext for bcrypt
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Password to hash
password = "core2020"

# Generate the hashed password
hashed_password = pwd_context.hash(password)
print("Hashed password:", hashed_password)

