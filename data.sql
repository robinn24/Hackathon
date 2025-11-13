-- Liste des employés

INSERT INTO employees (
    first_name, last_name, contract_type, weekly_hours_max, accept_replacement, supervisor_id, notes
) VALUES
    ('Alice', 'Johnson', 'Full-time', 40, 1, NULL, 'Project manager'),
    ('Bob', 'Smith', 'Part-time', 20, 0, 1, 'Specializes in electronics'),
    ('Charlie', 'Nguyen', 'Intern', 15, 1, 1, 'Learning embedded systems');
    
-- Liste des skills

INSERT INTO skills (name) VALUES
    ('Accueil'),
    ('Conseiller'),
    ('Directeur'),
    ('PCB Design'),
    ('Project Management');

-- Liaison des employés aux skills

INSERT INTO employee_skills (employee_id, skill_id) VALUES
    (1, 1), -- Alice knows Project Management
    (2, 1), -- Bob knows C Programming
    (2, 2), -- Bob knows Soldering
    (2, 3), -- Bob knows PCB Design
    (3, 1), -- Charlie knows C Programming
    (3, 2); -- Charlie knows Python

-- Rajout des tâches

INSERT INTO tasks (
    title, description, duration_hours, deadline, priority, assigned_to, status, location, cost_estimate
) VALUES
    ('Design PCB for sensor module', 'Create and test a PCB for the new sensor system.', 10, '2025-11-20', 'High', 2, 'Pending', 'Lab 1', 500.0),
    ('Program microcontroller firmware', 'Develop and flash firmware for temperature control.', 8, '2025-11-18', 'Critical', 3, 'Pending', 'Lab 2', 0.0),
    ('Prepare project report', 'Compile all results into a presentation.', 5, '2025-11-25', 'Medium', 1, 'Pending', 'Office', 100.0);
    
-- Liaison des skills néceccaires aux tâches

INSERT INTO task_required_skills (task_id, skill_id) VALUES
    (1, 4), -- PCB Design
    (1, 3), -- Soldering
    (2, 1), -- C Programming
    (2, 2), -- Python
    (3, 5); -- Project Management

-- Disponibilités de chaque employé

INSERT INTO employee_availability (employee_id, day_of_week, start_time, end_time) VALUES
    (1, 'Mon', '09:00', '17:00'),
    (1, 'Tue', '09:00', '17:00'),
    (2, 'Mon', '09:00', '13:00'),
    (2, 'Wed', '09:00', '13:00'),
    (3, 'Tue', '10:00', '16:00'),
    (3, 'Thu', '10:00', '16:00');

-- Liaison des employés et des tâches au planning

INSERT INTO planning (
    employee_id, task_id, date, start_time, end_time, validated_by_rh
) VALUES
    (2, 1, '2025-11-14', '09:00', '13:00', 1), -- Bob works on PCB Design
    (3, 2, '2025-11-15', '10:00', '16:00', 0), -- Charlie codes firmware
    (1, 3, '2025-11-18', '09:00', '12:00', 1); -- Alice prepares report

-- Absences de chacun

INSERT INTO absences (
    employee_id, start_date, end_date, reason, status
) VALUES
    (2, '2025-11-19', '2025-11-22', 'Personal leave', 'Approved');