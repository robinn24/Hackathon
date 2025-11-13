-- ========================================================
-- EMPLOYEES
-- ========================================================
CREATE TABLE IF NOT EXISTS employees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    contract_type TEXT CHECK(contract_type IN ('Full-time', 'Part-time', 'Intern', 'Contractor')),
    weekly_hours_max INTEGER CHECK(weekly_hours_max > 0),
--  hourly_cost REAL CHECK(hourly_cost >= 0),
    accept_replacement BOOLEAN DEFAULT 0,
    supervisor_id INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    notes TEXT,
    UNIQUE(first_name, last_name)
);

-- ========================================================
-- SKILLS
-- ========================================================
CREATE TABLE IF NOT EXISTS skills (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL
);

-- ========================================================
-- EMPLOYEE ↔ SKILLS (Many-to-Many)
-- ========================================================
CREATE TABLE IF NOT EXISTS employee_skills (
    employee_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (employee_id, skill_id)
);

-- ========================================================
-- AVAILABILITY (Normalized)
-- ========================================================
CREATE TABLE IF NOT EXISTS employee_availability (
    employee_id INTEGER NOT NULL,
    day_of_week TEXT CHECK(day_of_week IN ('Mon','Tue','Wed','Thu','Fri','Sat','Sun')),
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    PRIMARY KEY (employee_id, day_of_week, start_time)
);

-- ========================================================
-- TASKS
-- ========================================================
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    duration_hours INTEGER CHECK(duration_hours > 0),
    deadline TEXT,
    priority TEXT CHECK(priority IN ('Low', 'Medium', 'High', 'Critical')) DEFAULT 'Medium',
    assigned_to INTEGER REFERENCES employees(id) ON DELETE SET NULL,
    status TEXT CHECK(status IN ('Pending', 'In progress', 'Completed', 'Cancelled')) DEFAULT 'Pending',
    location TEXT,
    cost_estimate REAL CHECK(cost_estimate >= 0)
);

-- ========================================================
-- TASK ↔ REQUIRED SKILLS (Many-to-Many)
-- ========================================================
CREATE TABLE IF NOT EXISTS task_required_skills (
    task_id INTEGER NOT NULL,
    skill_id INTEGER NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (task_id, skill_id)
);

-- ========================================================
-- PLANNING (Task assignments on specific dates/times)
-- ========================================================
CREATE TABLE IF NOT EXISTS planning (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    task_id INTEGER NOT NULL,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    pause TEXT NOT NULL,
    validated_by_rh BOOLEAN DEFAULT 0,
    last_update TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    UNIQUE (employee_id, date, start_time) -- Prevent duplicate scheduling
);

-- ========================================================
-- ABSENCES
-- ========================================================
CREATE TABLE IF NOT EXISTS absences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    employee_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    reason TEXT,
    status TEXT CHECK(status IN ('Pending', 'Approved', 'Rejected')) DEFAULT 'Pending',
    FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
);

-- ========================================================
-- INDEXES (for faster lookups)
-- ========================================================
CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_planning_employee_id ON planning(employee_id);
CREATE INDEX IF NOT EXISTS idx_planning_task_id ON planning(task_id);
CREATE INDEX IF NOT EXISTS idx_absences_employee_id ON absences(employee_id);

-- ========================================================
-- VIEW: Employee Schedule Overview
-- ========================================================
CREATE VIEW IF NOT EXISTS v_employee_schedule AS
SELECT 
    e.id AS employee_id,
    e.first_name || ' ' || e.last_name AS employee_name,
    t.title AS task_title,
    t.priority,
    p.date,
    p.start_time,
    p.end_time,
    p.validated_by_rh,
    t.status AS task_status
FROM planning p
JOIN employees e ON e.id = p.employee_id
JOIN tasks t ON t.id = p.task_id;
