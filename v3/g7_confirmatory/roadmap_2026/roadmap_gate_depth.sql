WITH roadmap(phase, completed_gates, name, state, phase_order) AS (
  VALUES
    ('R0', 1, 'governance and roadmap freeze', 'current', 0),
    ('R1', 2, 'sensitivity provenance recovery', 'future gated', 1),
    ('R2', 4, 'runtime and detector qualification', 'future gated', 2),
    ('R3', 5, 'attack-mechanism atlas', 'development only', 3),
    ('R4', 7, 'search-arm and knowledge causality', 'development only', 4),
    ('R5', 8, 'passive detector bakeoff', 'development only', 5),
    ('R6', 9, 'explicit network and compound attacks', 'future gated', 6),
    ('R7', 10, 'adaptive defense-aware red team', 'development only', 7),
    ('R8', 11, 'active-defense harm-cost frontier', 'development only', 8),
    ('R9', 12, 'single locked confirmatory evaluation', 'SEALED', 9),
    ('R10', 13, 'external validity and publication', 'future', 10)
)
SELECT phase, completed_gates, name, state
FROM roadmap
ORDER BY phase_order;
