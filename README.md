# hearings
How do Congressional Hearings Change?


```bash
pip install -r requirements.txt
createdb hearings
export DATABASE_URL=postgresql:///hearings
pupa dbinit us
pupa party add Republican
pupa party add Democrat
pupa party add Republican-Conservative
pupa party add "Popular Democrat"
pupa party add "AL"
pupa party add "Independent"
pupa party add "Democratic-Liberal"
pupa party add "New Progressive"
pupa party add "Conservative"
pupa party add "Ind. Democrat"
pupa party add "Democrat-Liberal"
pupa update us
```

