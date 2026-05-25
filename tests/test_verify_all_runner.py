import scripts.verify_all as verify_all


def test_verify_all_runs_every_objective_gate(monkeypatch):
    seen = []

    def fake_run(label, args, env=None):
        seen.append((label, args))
        return 0

    monkeypatch.setattr(verify_all, "_run", fake_run)

    assert verify_all.main() == 0
    labels = [label for label, _ in seen]
    assert labels == [
        "compileall",
        "pytest",
        "nanobot latest",
        "telegram api surface",
        "gateway offline",
        "telegram live",
    ]
