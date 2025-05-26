# ✅ 1. โคลนโปรเจกต์จาก GitHub

git clone https://github.com/pakkadZ/robot_findxy.git

cd robot_findxy

# ✅ 2. ตรวจสอบ Python เวอร์ชัน (ควรเป็น Python 3.10)
python --version

# ✅ 3. สร้าง Virtual Environment
python -m venv .venv

# ✅ 4. เปิดใช้งาน Virtual Environment
# 👉 Windows:
.venv\Scripts\activate

# 👉 macOS / Linux:
source .venv/bin/activate

# ✅ 5. ติดตั้งไลบรารีทั้งหมด
pip install -r requirements.txt

# ✅ 6. สร้างโฟลเดอร์ (ถ้ายังไม่มี)
mkdir -p ai pic src runs/detect/train

# ✅ 7. รันโปรแกรม
python src/Main_robot.py
