# Graph Report - coursepaper  (2026-11-20)

## Corpus Check
- Corpus is ~34,848 words - fits in a single context window. You may not need a graph.

## Summary
- 1370 nodes · 3781 edges · 84 communities (54 shown, 30 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 418 edges (avg confidence: 0.91)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- ContestData references
- Accounts references
- education/presentation/http.py references
- education/application/ports.py references
- Domain and integration tests
- Document references
- Architecture and verification
- contest/presentation/http.py references
- PostgresContestData references
- Teaching screens and routing
- auth/presentation/http.py references
- EducationData references
- GitHub check jobs
- contest/api.py references
- Account and lesson screens
- contracts.py references
- Frontend libraries and localization
- Frontend domain models
- Contest HTTP security
- submissions.py references
- Problem references
- Browser sessions and events
- teaching.tsx references
- worker.py references
- Judge0 credentials and limits
- Accounts and sessions
- Progress references
- Backend service configuration
- RabbitMQ publishing and retries
- check_owner references
- dependencies references
- Editor and attempt history
- Alembic migration history
- services references
- Integration judge fixture
- Backend container builds
- TypeScript compiler configuration
- Shared dependency readiness
- lifespan references
- Judge0 execution API
- Judge0 sandbox build
- Pre-commit quality hooks
- structure references
- MongoEducation references
- Judge0 PostgreSQL health
- Shared storage healthchecks
- rabbit references
- healthcheck references
- Judge0 network isolation
- Judge0 storage startup
- redis references
- REST load measurement
- Auth container startup
- Contest container startup
- Gateway and service topology
- Education worker startup
- Judge0 Redis container
- App persistence volumes
- Contest orchestration
- postgres-init.sh references
- setup.sh references
- codeforge references

## God Nodes (most connected - your core abstractions)
1. `Document` - 292 edges
2. `User` - 93 edges
3. `Problem` - 77 edges
4. `EducationData` - 52 edges
5. `ContestData` - 51 edges
6. `MongoEducationData` - 46 edges
7. `PostgresContestData` - 44 edges
8. `api()` - 38 edges
9. `Contests` - 37 edges
10. `Content` - 37 edges

## Surprising Connections (you probably didn't know these)
- `Auth` --implements--> `Accounts`  [INFERRED]
  documentation/architecture.md → app/codeforge/auth/application/accounts.py
- `judge.request` --implements--> `connect()`  [INFERRED]
  documentation/architecture.md → app/codeforge/common/broker.py
- `Сессия RS256` --implements--> `Tokens`  [INFERRED]
  documentation/architecture.md → app/codeforge/common/security.py
- `Contest` --implements--> `Contests`  [INFERRED]
  documentation/architecture.md → app/codeforge/contest/application/rooms.py
- `Education` --implements--> `Content`  [INFERRED]
  documentation/architecture.md → app/codeforge/education/application/content.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Учебная проверка и начисление XP** — documentation_architecture_учебная_попытка, documentation_architecture_judge_request, documentation_architecture_worker_judge0, documentation_architecture_учебный_xp [EXTRACTED 1.00]
- **Хранилища интеграционных тестов** — documentation_verification_интеграционные_тесты, documentation_architecture_postgresql, documentation_architecture_mongodb, documentation_architecture_redis, documentation_architecture_rabbitmq [EXTRACTED 1.00]
- **Слои и порты микросервисов** — documentation_architecture_слои_микросервисов, documentation_architecture_domain, documentation_architecture_application, documentation_architecture_infrastructure, documentation_architecture_presentation, documentation_architecture_порты_сценариев [EXTRACTED 1.00]

## Communities (84 total, 30 thin omitted)

### Community 0 - "ContestData references"
Cohesion: 0.06
Nodes (23): CodeSubmission, ContestData, ContestRepository, RoomDraft, StandingsCache, TaskBank, Contests, overview() (+15 more)

### Community 1 - "Accounts references"
Cohesion: 0.06
Nodes (15): Accounts, require_account(), require_admin(), AccessSigner, AccountRepository, AccountTransaction, DuplicateAccount, Passwords (+7 more)

### Community 2 - "education/presentation/http.py references"
Cohesion: 0.08
Nodes (49): SubmissionDraft, answers(), attempt(), author_task(), complete(), contest_tasks(), course(), courses() (+41 more)

### Community 3 - "education/application/ports.py references"
Cohesion: 0.06
Nodes (23): get_cases(), JudgeSubmissions, DuplicateCourse, JudgementRepository, JudgeUnavailable, ModuleDraft, Runner, local_time() (+15 more)

### Community 4 - "Domain and integration tests"
Cohesion: 0.10
Nodes (23): check_password(), hash_password(), password_bytes(), task_xp(), csv_gradebook(), imports(), test_service_dependencies_point_inward(), within() (+15 more)

### Community 5 - "Document references"
Cohesion: 0.09
Nodes (4): Document, from_mongo(), MongoEducationData, to_mongo()

### Community 6 - "Architecture and verification"
Cohesion: 0.06
Nodes (35): Application, Auth, Contest, Domain, Education, Infrastructure, judge.request, MongoDB replica set (+27 more)

### Community 7 - "contest/presentation/http.py references"
Cohesion: 0.12
Nodes (18): attempt(), create(), details(), edit(), events(), get_service(), invite(), join() (+10 more)

### Community 9 - "Teaching screens and routing"
Cohesion: 0.17
Nodes (32): useLoad(), useSession(), api(), request(), NotFound(), Credentials(), submit(), ProfilePage() (+24 more)

### Community 10 - "auth/presentation/http.py references"
Cohesion: 0.15
Nodes (18): accounts(), change_access(), edit_profile(), login(), logout(), me(), public_user(), refresh() (+10 more)

### Community 11 - "EducationData references"
Cohesion: 0.08
Nodes (5): archive(), save(), save(), EducationData, save()

### Community 12 - "GitHub check jobs"
Cohesion: 0.08
Nodes (29): run, CODEFORGE_ADMIN_PASSWORD, CODEFORGE_DEMO_PASSWORD, CODEFORGE_TEST_ADMIN, CODEFORGE_TEST_URL, SECURE_COOKIE, defaults, runs-on (+21 more)

### Community 13 - "contest/api.py references"
Cohesion: 0.11
Nodes (8): RedisLiveEvents, RedisSubmissionLimiter, recurring(), lifespan(), PostgresContests, EducationTaskBank, RedisStandingsCache, test_background_publisher_retries_after_one_failure()

### Community 14 - "Account and lesson screens"
Cohesion: 0.18
Nodes (22): sendEducation(), useLive(), Lesson, Profile, Question, typeNames, session, Topic (+14 more)

### Community 15 - "contracts.py references"
Cohesion: 0.16
Nodes (3): application(), BackgroundJob, Settings

### Community 16 - "Frontend libraries and localization"
Cohesion: 0.10
Nodes (25): devDependencies, tailwindcss@4.1.17, @tailwindcss/vite@4.1.17, @types/node@^20.19.0, @types/react@^18.3.0, @types/react-dom@^18.3.0, typescript@~5.9.3, vite@^6.4.0 (+17 more)

### Community 17 - "Frontend domain models"
Cohesion: 0.11
Nodes (24): Attempt, AuthorQuestion, Course, CourseCard, difficultyNames, languageNames, LessonDraft, Problem (+16 more)

### Community 18 - "Contest HTTP security"
Cohesion: 0.13
Nodes (7): User, socket_user(), stream(), optional_user(), signed_in(), Tokens, events()

### Community 19 - "submissions.py references"
Cohesion: 0.20
Nodes (8): LiveEvents, SubmissionLimiter, EducationRepository, JudgementQueue, PracticeLimiter, public_submission(), Submissions, now()

### Community 20 - "Problem references"
Cohesion: 0.17
Nodes (6): Problem, fetch(), Content, save(), public_task(), expose()

### Community 21 - "Browser sessions and events"
Cohesion: 0.13
Nodes (18): education, Loading, SessionContext, SessionProvider(), SessionState, Identity, LiveEvent, ApiError (+10 more)

### Community 22 - "teaching.tsx references"
Cohesion: 0.15
Nodes (17): CourseFields, Gradebook, moveItem(), TaskDraft, AuthorCourse, BackToTeaching(), blankCourse, blankQuestion() (+9 more)

### Community 23 - "worker.py references"
Cohesion: 0.22
Nodes (9): main(), connect(), main(), call(), course(), login(), main(), seed() (+1 more)

### Community 24 - "Judge0 credentials and limits"
Cohesion: 0.19
Nodes (20): ALLOW_ENABLE_NETWORK, AUTHN_TOKEN, COUNT, ENABLE_ADDITIONAL_FILES, ENABLE_BATCHED_SUBMISSIONS, ENABLE_CALLBACKS, ENABLE_NETWORK, JUDGE0_TELEMETRY_ENABLE (+12 more)

### Community 25 - "Accounts and sessions"
Cohesion: 0.19
Nodes (7): lifespan(), create(), BcryptPasswords, RedisSessions, postgres(), resources(), settings()

### Community 26 - "Progress references"
Cohesion: 0.22
Nodes (10): Progress, save(), save(), save(), changes(), grant(), level(), streaks() (+2 more)

### Community 27 - "Backend service configuration"
Cohesion: 0.22
Nodes (19): environment, environment, environment, environment, AUTH_DB, CONTEST_DB, EDUCATION_URL, FORWARDED_ALLOW_IPS (+11 more)

### Community 28 - "RabbitMQ publishing and retries"
Cohesion: 0.16
Nodes (8): Broker, Handler, publish_pending(), RabbitJudgements, test_cancelled_transport_confirmation_is_retryable(), test_publisher_honors_explicit_shutdown_cancellation(), pending(), waiting()

### Community 29 - "check_owner references"
Cohesion: 0.20
Nodes (5): check_owner(), archive(), save(), require_teacher(), CourseDraft

### Community 30 - "dependencies references"
Cohesion: 0.11
Nodes (17): dependencies, highlight.js@^11.11.1, i18next@^25.6.0, lucide-react@^0.468.0, monaco-editor@^0.52.2, react@18.3.1, react-dom@18.3.1, react-i18next@^16.2.0 (+9 more)

### Community 31 - "Editor and attempt history"
Cohesion: 0.22
Nodes (12): useEducation(), Language, LanguageSelect(), snippets, AttemptHistory(), AttemptPage(), CodeOutput(), Highlighted() (+4 more)

### Community 33 - "services references"
Cohesion: 0.12
Nodes (15): internal, command, image, networks, volumes, networks, data, edge (+7 more)

### Community 34 - "Integration judge fixture"
Cohesion: 0.12
Nodes (15): judge-fixture, depends_on, environment, JUDGE_AUTH_TOKEN, JUDGE_TRUSTED_LIMITS, JUDGE_URL, command, condition (+7 more)

### Community 35 - "Backend container builds"
Cohesion: 0.18
Nodes (15): build, context, dockerfile, network, build, build, build, build (+7 more)

### Community 36 - "TypeScript compiler configuration"
Cohesion: 0.13
Nodes (14): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noUnusedLocals, noUnusedParameters (+6 more)

### Community 37 - "Shared dependency readiness"
Cohesion: 0.23
Nodes (13): depends_on, depends_on, mongo, postgres, rabbit, redis, depends_on, depends_on (+5 more)

### Community 38 - "lifespan references"
Cohesion: 0.23
Nodes (3): lifespan(), RedisCourseCache, RedisPracticeLimiter

### Community 39 - "Judge0 execution API"
Cohesion: 0.18
Nodes (11): environment, networks, JUDGE_AUTH_TOKEN, JUDGE_URL, image, networks, privileged, restart (+3 more)

### Community 40 - "Judge0 sandbox build"
Cohesion: 0.22
Nodes (10): context, dockerfile, build, command, image, networks, privileged, restart (+2 more)

### Community 41 - "Pre-commit quality hooks"
Cohesion: 0.20
Nodes (9): entry, id, language, name, pass_filenames, types, repos, hooks (+1 more)

### Community 44 - "Judge0 PostgreSQL health"
Cohesion: 0.22
Nodes (9): interval, retries, test, timeout, healthcheck, image, networks, volumes (+1 more)

### Community 46 - "Shared storage healthchecks"
Cohesion: 0.25
Nodes (8): AUTH_PASSWORD, CONTEST_PASSWORD, POSTGRES_PASSWORD, environment, image, networks, volumes, postgres

### Community 47 - "rabbit references"
Cohesion: 0.25
Nodes (8): RABBITMQ_DEFAULT_PASS, RABBITMQ_DEFAULT_USER, environment, hostname, image, networks, volumes, rabbit

### Community 48 - "healthcheck references"
Cohesion: 0.57
Nodes (8): interval, retries, test, timeout, healthcheck, healthcheck, healthcheck, healthcheck

### Community 49 - "Judge0 network isolation"
Cohesion: 0.25
Nodes (7): internal, internal, networks, execution, judge-data, volumes, judge-pg

### Community 50 - "Judge0 storage startup"
Cohesion: 0.25
Nodes (8): judge-db, judge-redis, judge-server, condition, condition, depends_on, condition, depends_on

### Community 52 - "redis references"
Cohesion: 0.29
Nodes (7): REDIS_PASSWORD, command, environment, image, networks, volumes, redis

### Community 53 - "REST load measurement"
Cohesion: 0.29
Nodes (5): password, paths, suffix, task, users

### Community 54 - "Auth container startup"
Cohesion: 0.33
Nodes (6): command, image, networks, restart, volumes, auth

### Community 55 - "Contest container startup"
Cohesion: 0.33
Nodes (6): command, image, networks, restart, volumes, contest

### Community 56 - "Gateway and service topology"
Cohesion: 0.33
Nodes (6): command, image, networks, restart, volumes, education-api

### Community 57 - "Education worker startup"
Cohesion: 0.33
Nodes (6): command, image, networks, restart, volumes, education-worker

### Community 58 - "Judge0 Redis container"
Cohesion: 0.33
Nodes (6): REDIS_PASSWORD, command, environment, image, networks, judge-redis

### Community 59 - "App persistence volumes"
Cohesion: 0.40
Nodes (5): volumes, mongo, postgres, rabbit, redis

## Knowledge Gaps
- **8 isolated node(s):** `codeforge`, `Модуль main.tsx`, `Redis`, `Турнирный снимок задачи`, `Domain` (+3 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 330 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **30 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Document` connect `Document references` to `ContestData references`, `Accounts references`, `education/presentation/http.py references`, `education/application/ports.py references`, `Domain and integration tests`, `contest/presentation/http.py references`, `PostgresContestData references`, `auth/presentation/http.py references`, `EducationData references`, `contest/api.py references`, `contracts.py references`, `Contest HTTP security`, `submissions.py references`, `Problem references`, `worker.py references`, `Accounts and sessions`, `Progress references`, `RabbitMQ publishing and retries`, `check_owner references`, `lifespan references`, `structure references`, `MongoEducation references`, `Backend dependencies`, `mongo.py references`, `Contest orchestration`, `__init__ references`?**
  _High betweenness centrality (0.309) - this node is a cross-community bridge._
- **Are the 92 inferred relationships involving `Document` (e.g. with `Accounts` and `AccountTransaction`) actually correct?**
  _`Document` has 92 INFERRED edges - model-reasoned connections that need verification._
- **What connects `codeforge`, `Модуль main.tsx`, `Redis` to the rest of the system?**
  _8 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `ContestData references` be split into smaller, more focused modules?**
  _Cohesion score 0.06473960821786909 - nodes in this community are weakly interconnected._
- **Why does `React SPA` connect `Architecture and verification` to `Account and lesson screens`?**
  _High betweenness centrality (0.102) - this node is a cross-community bridge._
- **Are the 23 inferred relationships involving `User` (e.g. with `Accounts` and `require_admin()`) actually correct?**
  _`User` has 23 INFERRED edges - model-reasoned connections that need verification._
- **Should `Accounts references` be split into smaller, more focused modules?**
  _Cohesion score 0.057181942544459644 - nodes in this community are weakly interconnected._
## Extraction checks

- Source coverage: 97 code and configuration files, plus 4 documentation files.
- Raw edges with unresolved endpoints: 229.
- Raw edges sharing an undirected endpoint pair: 269.
- Semantic extraction ran in the local assistant. Token usage could not be measured.
