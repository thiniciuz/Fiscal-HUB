# Valores centralizados para a UI (labels, ordens, etc.)

# Regimes (sem "Todas" - essa opção é só para filtros de tela)
REGIMES = [
    "Simples Nacional",
    "Lucro Presumido",
    "Lucro Real",
]

REGIMES_ALL = ["Todas"] + REGIMES

# Status (ordem e labels)
STATUS_ORDER = ["PENDENTE", "EM_ANDAMENTO", "CONCLUIDA", "ENVIADA"]
STATUS_LABELS = {
    "PENDENTE": "Pendente",
    "EM_ANDAMENTO": "Em andamento",
    "CONCLUIDA": "Concluída",
    "ENVIADA": "Enviada",
}

# Tipos (TaskType)
TYPE_LABELS = {
    "OBR": "Obrigação",
    "ACS": "Acessória",
}

# Órgãos (TaskOrgao)
ORGAO_LABELS = {
    "MUN": "MUN",
    "EST": "EST",
    "FED": "FED",
}
