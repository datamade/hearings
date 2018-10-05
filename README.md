# hearings
How do Congressional Hearings Change?


```bash
pip install -r requirements.txt
createdb hearings
export DATABASE_URL=postgresql:///hearings
pupa dbinit us
pupa update us
```

