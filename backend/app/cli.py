"""Command-line tools for the report and the demo.

    python -m app.cli eval            print the NFR-AI table, save eval_report.json
    python -m app.cli reset-demo      delete and recreate the Suresh / Anita demo accounts
"""
import json
import sys

from .db import Base, SessionLocal, engine
from .models import User
from .services.evaluation import run_evaluation
from .services.seed import purge_user, seed_demo


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if cmd == "eval":
            rep = run_evaluation(db)
            print(f"Provider: {rep['provider']}   Queries: {rep['corpus']['queries']}   Statements: {rep['statements']}\n")
            for m in rep["metrics"]:
                print(f"{m['id']:<9} {m['label']:<48} target {m['target']:<7} measured {m['value']:<6} "
                      f"{'PASS' if m['passed'] else 'FAIL'}")
            acc = rep["answer_accuracy"]
            print(f"\nAnswer accuracy: {acc['value']}% ({acc['correct']}/{acc['total']})")
            fails = [r for r in rep["rows"] if not r["passed"]]
            for r in fails:
                print(f"  FAILED [{r['type']}] {r['question']} -> {r['answer'][:90]}")
            with open("eval_report.json", "w", encoding="utf-8") as f:
                json.dump(rep, f, indent=2, ensure_ascii=False)
            print("\nSaved eval_report.json")
        elif cmd == "reset-demo":
            for email in ("suresh@demo.in", "anita@demo.in"):
                u = db.query(User).filter(User.email == email).first()
                if u:
                    purge_user(db, u.id)
            others = db.query(User).filter(User.is_system.is_(False)).count()
            if others:
                print(f"{others} other account(s) exist, so demo accounts are only created on an empty database.")
                print("Delete the database file (local) or use a fresh Neon branch to reseed.")
            else:
                seed_demo(db)
                print("Demo accounts recreated: suresh@demo.in / anita@demo.in, password demo1234")
        else:
            print(__doc__)
    finally:
        db.close()


if __name__ == "__main__":
    main()
