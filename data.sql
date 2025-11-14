-- ============================
-- Employés
-- ============================
INSERT INTO employees (
  first_name, last_name, contract_type, weekly_hours_max, accept_replacement, supervisor_id, notes
) VALUES
  ('Alice',   'Johnson', 'Full-time', 40, 1, NULL, 'Project manager'),
  ('Bob',     'Smith',   'Part-time', 20, 0, 1,    'Specializes in electronics'),
  ('Charlie', 'Nguyen',  'Intern',    15, 1, 1,    'Learning embedded systems'),
  ('Diana',   'Lee',     'Contractor',30, 1, 1,    'PCB & Soldering specialist'),
  ('Eve',     'Martin',  'Part-time', 20, 1, 1,    'PM backup');

-- ============================
-- Compétences
-- ============================
INSERT INTO skills (name) VALUES
  ('C Programming'),
  ('Python'),
  ('Soldering'),
  ('PCB Design'),
  ('Project Management');

-- ============================
-- Compétences par employé
-- ============================
-- Alice
INSERT INTO employee_skills (employee_id, skill_id) VALUES (1, 5);
-- Bob
INSERT INTO employee_skills (employee_id, skill_id) VALUES (2, 1);
INSERT INTO employee_skills (employee_id, skill_id) VALUES (2, 3);
INSERT INTO employee_skills (employee_id, skill_id) VALUES (2, 4);
-- Charlie
INSERT INTO employee_skills (employee_id, skill_id) VALUES (3, 1);
INSERT INTO employee_skills (employee_id, skill_id) VALUES (3, 2);
-- Diana
INSERT INTO employee_skills (employee_id, skill_id) VALUES (4, 3);
INSERT INTO employee_skills (employee_id, skill_id) VALUES (4, 4);
-- Eve
INSERT INTO employee_skills (employee_id, skill_id) VALUES (5, 5);

-- ============================
-- Disponibilités (corrigées et complétées)
-- ============================

-- Alice – Full-time : 40h → 5 × 8h
INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time) VALUES
  (1, 'Mon', '08:00', '16:00'),
  (1, 'Tue', '08:00', '16:00'),
  (1, 'Wed', '08:00', '16:00'),
  (1, 'Thu', '08:00', '16:00'),
  (1, 'Fri', '08:00', '16:00');

-- Bob – Part-time : 20h → 4 × 5h
INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time) VALUES
  (2, 'Mon', '08:00', '13:00'),
  (2, 'Tue', '08:00', '13:00'),
  (2, 'Wed', '08:00', '13:00'),
  (2, 'Thu', '08:00', '13:00');

-- Charlie – Intern : 15h → 3 × 5h
INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time) VALUES
  (3, 'Tue', '11:00', '16:00'),
  (3, 'Thu', '11:00', '16:00'),
  (3, 'Fri', '11:00', '16:00');

-- Diana – Contractor : 30h → 4 × 7h30
INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time) VALUES
  (4, 'Tue', '08:00', '15:30'),
  (4, 'Wed', '08:00', '15:30'),
  (4, 'Thu', '08:00', '15:30'),
  (4, 'Fri', '08:00', '15:30');

-- Eve – Part-time : 20h → 6h + 7h + 7h
INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time) VALUES
  (5, 'Thu', '09:00', '16:00'),
  (5, 'Fri', '09:00', '16:00'),
  (5, 'Sat', '10:00', '16:00');

-- ============================
-- Tâches
-- ============================
INSERT INTO tasks (
  title, description, duration_hours, deadline, priority, assigned_to, status, location, cost_estimate
) VALUES
  ('Design PCB for sensor module', 'Create and test a PCB for the new sensor system.', 10, '2025-11-25', 'High',      2, 'Pending', 'Lab 1', 500.0),
  ('Program microcontroller firmware', 'Develop and flash firmware for temperature control.', 8, '2025-11-20', 'Critical', 3, 'Pending', 'Lab 2', 0.0),
  ('Prepare project report', 'Compile all results into a presentation.', 5, '2025-11-25', 'Medium',     1, 'Pending', 'Office', 100.0);

-- ============================
-- Compétences requises par tâche
-- ============================

-- Task 1 : PCB Design + Soldering
INSERT INTO task_required_skills (task_id, skill_id) VALUES (1, 4);
INSERT INTO task_required_skills (task_id, skill_id) VALUES (1, 3);

-- Task 2 : C Programming + Python
INSERT INTO task_required_skills (task_id, skill_id) VALUES (2, 1);
INSERT INTO task_required_skills (task_id, skill_id) VALUES (2, 2);

-- Task 3 : Project Management
INSERT INTO task_required_skills (task_id, skill_id) VALUES (3, 5);

-- ============================
-- Planning (vide)
-- ============================
-- Intentionnellement vide

-- ============================
-- Absences (vide)
-- ============================
-- Intentionnellement vide
