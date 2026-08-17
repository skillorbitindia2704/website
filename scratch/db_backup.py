import os
import gzip
import shutil
import sqlite3
from datetime import datetime

def backup_database():
    print("Initializing Database Backup...")
    # Paths
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "instance", "skill_orbit_india.db")
    backup_dir = os.path.join(base_dir, "instance", "backups")
    
    if not os.path.exists(db_path):
        # Check parent folder for fallback
        db_path = os.path.join(base_dir, "skill_orbit_india.db")
        if not os.path.exists(db_path):
            print(f"ERROR: Database file not found at {db_path}")
            return False
            
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"backup_{timestamp}.db.gz"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    try:
        # Step 1: Create a safe copy of the active database to prevent locks during read
        temp_copy_path = os.path.join(backup_dir, f"temp_{timestamp}.db")
        shutil.copy2(db_path, temp_copy_path)
        
        # Step 2: Gzip compress the copied database
        with open(temp_copy_path, "rb") as f_in:
            with gzip.open(backup_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        # Clean up temp file
        os.remove(temp_copy_path)
        print(f"SUCCESS: Database backup created successfully at: {backup_path}")
        
        # Step 3: Verify the backup's integrity
        verify_backup(backup_path)
        
        # Step 4: Rotate backups (keep only last 7 copies)
        rotate_backups(backup_dir)
        return True
    except Exception as e:
        print(f"ERROR: Database backup failed: {e}")
        return False

def verify_backup(backup_path):
    print(f"Verifying integrity of backup: {os.path.basename(backup_path)}...")
    temp_verify_path = backup_path.replace(".gz", "_verify.db")
    try:
        # Decompress to temporary file
        with gzip.open(backup_path, "rb") as f_in:
            with open(temp_verify_path, "wb") as f_out:
                shutil.copyfileobj(f_in, f_out)
                
        # Connect and check integrity
        conn = sqlite3.connect(temp_verify_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()[0]
        conn.close()
        
        if result == "ok":
            print("INTEGRITY CHECK PASSED: SQLite database backup is valid!")
        else:
            print(f"INTEGRITY CHECK WARNING: Database check returned: {result}")
            
    except Exception as e:
        print(f"ERROR: Backup verification failed: {e}")
    finally:
        if os.path.exists(temp_verify_path):
            os.remove(temp_verify_path)

def rotate_backups(backup_dir):
    print("Checking for backup rotation...")
    backups = [os.path.join(backup_dir, f) for f in os.listdir(backup_dir) if f.startswith("backup_") and f.endswith(".db.gz")]
    # Sort by modification time (oldest first)
    backups.sort(key=os.path.getmtime)
    
    if len(backups) > 7:
        excess = len(backups) - 7
        print(f"Found {len(backups)} backups. Rotating out the {excess} oldest copy/copies...")
        for i in range(excess):
            try:
                os.remove(backups[i])
                print(f"Removed old backup: {os.path.basename(backups[i])}")
            except Exception as e:
                print(f"ERROR: Failed to remove old backup {backups[i]}: {e}")
    else:
        print(f"Rotation not needed: only {len(backups)}/7 backups exist.")

if __name__ == "__main__":
    backup_database()
