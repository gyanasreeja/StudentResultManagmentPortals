
import random
import sys
from datetime import datetime

from main import (Base, Result, SessionLocal, TopicResult, User, engine,
                  hash_password)

PER_DEPT_PER_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else 20
assert 1 <= PER_DEPT_PER_YEAR <= 150, "choose 1-150 students per dept per year"
CURRENT_YEAR = datetime.now().year
DEPTS = {"CSE": "510", "IT": "511", "ECE": "512", "EEE": "513", "MECH": "514", "CIVIL": "515"}
COLLEGE = "126"
PASSWORD = "Pass@1234"

# subjects every student has + 2 department-specific ones
COMMON = ["Math", "Science", "English"]
DEPT_SUBJECTS = {
    "CSE": ["Data Structures", "Operating Systems"],
    "IT": ["Database Systems", "Computer Networks"],
    "ECE": ["Digital Electronics", "Signals and Systems"],
    "EEE": ["Circuit Theory", "Power Systems"],
    "MECH": ["Thermodynamics", "Fluid Mechanics"],
    "CIVIL": ["Structural Analysis", "Surveying"],
}
# topics match the AI knowledge base in ai_recommend.py
TOPICS = {
    "Math": ["Trigonometry", "Algebra", "Geometry"],
    "Science": ["Chemical bonding", "Mechanics", "Photosynthesis"],
    "English": ["Grammar", "Comprehension", "Essay writing"],
}

FIRST = ["Aarav", "Vivaan", "Aditya", "Sai", "Arjun", "Rohan", "Karthik", "Varun", "Harsha", "Pranav",
         "Ananya", "Diya", "Sneha", "Priya", "Lakshmi", "Meghana", "Divya", "Pooja", "Sravani", "Keerthi",
         "Teja", "Naveen", "Charan", "Manoj", "Ramesh", "Bhavana", "Swathi", "Harini", "Nikhil", "Ravi"]
LAST = ["Reddy", "Sharma", "Patnala", "Naidu", "Rao", "Kumar", "Varma", "Raju", "Chowdary", "Prasad",
        "Gupta", "Kiran", "Murthy", "Babu", "Devi", "Yadav", "Goud", "Setty", "Mohan", "Das",
        "Nair", "Iyer", "Pillai", "Verma"]

rng = random.Random(42)  # fixed seed -> same data every run


def clamp(x, lo=0, hi=100):
    return max(lo, min(hi, x))


def half(x):
    return round(x * 2) / 2


def main():
    Base.metadata.create_all(bind=engine)
    pw_hash = hash_password(PASSWORD)  # hash once; bcrypt per student would be slow
    name_pool = [f"{f} {l}" for l in LAST for f in FIRST]
    rng.shuffle(name_pool)
    name_i = 0
    added = skipped = 0

    with SessionLocal() as db:
        existing = {u for (u,) in db.query(User.user_id).all()}
        for year in (1, 2, 3, 4):
            adm_yy = str(CURRENT_YEAR - year + 1)[-2:]  # 1st year joined this year, 4th joined 3 yrs ago
            for dept, code in DEPTS.items():
                dept_bias = rng.uniform(-4, 4)
                for n in range(PER_DEPT_PER_YEAR):
                    roll = f"A{adm_yy}{COLLEGE}{code}{101 + n}"
                    name = name_pool[name_i % len(name_pool)]
                    name_i += 1
                    if roll in existing:
                        skipped += 1
                        continue
                    db.add(User(user_id=roll, name=name, role="student", password=pw_hash,
                                department=dept, year=year))
                    existing.add(roll)

                    ability = rng.gauss(66 + dept_bias, 12)  # each student's overall level
                    for subj in COMMON + DEPT_SUBJECTS[dept]:
                        marks = half(clamp(rng.gauss(ability, 9)))
                        db.add(Result(student_roll=roll, student_name=name, subject=subj, marks=marks))
                    for subj, topics in TOPICS.items():
                        for t in topics:
                            mx = 20.0
                            pct = clamp(rng.gauss(ability, 16), 15, 100) / 100
                            db.add(TopicResult(student_roll=roll, subject=subj, topic=t,
                                               marks=half(pct * mx), max_marks=mx))
                    added += 1
            db.commit()
    print(f"Done. Added {added} students, skipped {skipped} existing.")


if __name__ == "__main__":
    main()