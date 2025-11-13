
-- 1A) Journal des événements
CREATE TABLE IF NOT EXISTS db_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,
    operation TEXT CHECK(operation IN ('INSERT','UPDATE','DELETE')) NOT NULL,
    row_id INTEGER,
    event_time TEXT DEFAULT (datetime('now')),
    processed INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_db_events_processed ON db_events(processed, event_time);

-- 1B) Table pour stocker les propositions IA (aucune modification du planning en place)
CREATE TABLE IF NOT EXISTS ai_planning_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT DEFAULT (datetime('now')),
    source_event_ids TEXT,              -- liste d’IDs d’événements agrégés
    proposal_version TEXT,              -- p.ex. hash de prompt/contexte
    rationale TEXT,                     -- explications de l’agent
    status TEXT CHECK(status IN ('Draft','Applied','Rejected')) DEFAULT 'Draft'
);

-- Détails des créneaux proposés (sans toucher à "planning")
CREATE TABLE IF NOT EXISTS ai_proposal_slots (
    proposal_id INTEGER NOT NULL REFERENCES ai_planning_proposals(id) ON DELETE CASCADE,
    task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    employee_id INTEGER NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    UNIQUE (proposal_id, employee_id, date, start_time)
);
CREATE INDEX IF NOT EXISTS idx_ai_proposal_slots_proposal ON ai_proposal_slots(proposal_id);

-- 1C) Helpers pour générer les triggers
-- (fonction utilitaire via temp table pour DRY ; si non souhaité, dupliquer les 3 triggers par table)
-- NB: SQLite ne supporte pas les procédures ; on écrit explicitement les triggers ci-dessous.

-- EMPLOYEES
CREATE TRIGGER IF NOT EXISTS trg_employees_ai_ins AFTER INSERT ON employees
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employees','INSERT', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_employees_ai_upd AFTER UPDATE ON employees
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employees','UPDATE', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_employees_ai_del AFTER DELETE ON employees
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employees','DELETE', OLD.id);
END;

-- SKILLS
CREATE TRIGGER IF NOT EXISTS trg_skills_ai_ins AFTER INSERT ON skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('skills','INSERT', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_skills_ai_upd AFTER UPDATE ON skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('skills','UPDATE', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_skills_ai_del AFTER DELETE ON skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('skills','DELETE', OLD.id);
END;

-- EMPLOYEE_SKILLS
CREATE TRIGGER IF NOT EXISTS trg_employee_skills_ai_ins AFTER INSERT ON employee_skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employee_skills','INSERT', NEW.employee_id);
END;
CREATE TRIGGER IF NOT EXISTS trg_employee_skills_ai_upd AFTER UPDATE ON employee_skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employee_skills','UPDATE', NEW.employee_id);
END;
CREATE TRIGGER IF NOT EXISTS trg_employee_skills_ai_del AFTER DELETE ON employee_skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employee_skills','DELETE', OLD.employee_id);
END;

-- EMPLOYEE_AVAILABILITY
CREATE TRIGGER IF NOT EXISTS trg_employee_availability_ai_ins AFTER INSERT ON employee_availability
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employee_availability','INSERT', NEW.employee_id);
END;
CREATE TRIGGER IF NOT EXISTS trg_employee_availability_ai_upd AFTER UPDATE ON employee_availability
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employee_availability','UPDATE', NEW.employee_id);
END;
CREATE TRIGGER IF NOT EXISTS trg_employee_availability_ai_del AFTER DELETE ON employee_availability
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('employee_availability','DELETE', OLD.employee_id);
END;

-- TASKS
CREATE TRIGGER IF NOT EXISTS trg_tasks_ai_ins AFTER INSERT ON tasks
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('tasks','INSERT', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_tasks_ai_upd AFTER UPDATE ON tasks
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('tasks','UPDATE', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_tasks_ai_del AFTER DELETE ON tasks
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('tasks','DELETE', OLD.id);
END;

-- TASK_REQUIRED_SKILLS
CREATE TRIGGER IF NOT EXISTS trg_task_required_skills_ai_ins AFTER INSERT ON task_required_skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('task_required_skills','INSERT', NEW.task_id);
END;
CREATE TRIGGER IF NOT EXISTS trg_task_required_skills_ai_upd AFTER UPDATE ON task_required_skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('task_required_skills','UPDATE', NEW.task_id);
END;
CREATE TRIGGER IF NOT EXISTS trg_task_required_skills_ai_del AFTER DELETE ON task_required_skills
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('task_required_skills','DELETE', OLD.task_id);
END;

-- PLANNING (utile si on souhaite que les modifs RH régénèrent une proposition ; on peut désactiver si besoin)
CREATE TRIGGER IF NOT EXISTS trg_planning_ai_ins AFTER INSERT ON planning
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('planning','INSERT', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_planning_ai_upd AFTER UPDATE ON planning
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('planning','UPDATE', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_planning_ai_del AFTER DELETE ON planning
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('planning','DELETE', OLD.id);
END;

-- ABSENCES
CREATE TRIGGER IF NOT EXISTS trg_absences_ai_ins AFTER INSERT ON absences
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('absences','INSERT', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_absences_ai_upd AFTER UPDATE ON absences
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('absences','UPDATE', NEW.id);
END;
CREATE TRIGGER IF NOT EXISTS trg_absences_ai_del AFTER DELETE ON absences
BEGIN
  INSERT INTO db_events(table_name, operation, row_id) VALUES('absences','DELETE', OLD.id);
END;
