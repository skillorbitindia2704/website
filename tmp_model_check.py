import sys
sys.path.insert(0, '.')
from models.user import User
from models.hr import Employee
print('User has employee_profile attribute:', hasattr(User, 'employee_profile'))
print('Employee has user attribute:', hasattr(Employee, 'user'))
print('User mapper props:', [p.key for p in User.__mapper__.iterate_properties])
print('Employee mapper props:', [p.key for p in Employee.__mapper__.iterate_properties])
