"""
=============================================================
  SEDRA — Gerenciador de Tarefas
  Versão: V1.0
=============================================================
"""

import os
from flask import Flask, render_template, request, jsonify
from database import db, AtividadeGerenciador, HistoricoCard, ConfigGerenciador, Usuario
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "sedra-gerenciador-chave-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

_db_url = os.environ.get("DATABASE_URL", "")
if _db_url.startswith("postgres://"):
    _db_url = _db_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = (
    _db_url or "sqlite:///" + os.path.join(BASE_DIR, "instance", "gerenciador.db")
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

os.makedirs(os.path.join(BASE_DIR, "instance"), exist_ok=True)

db.init_app(app)

STATUSES   = ["Em andamento", "Aguardando", "Em revisão", "Concluído"]
PRIORITIES = ["Baixa", "Média", "Alta", "Urgente"]
DEFAULT_AREAS = ["Administrativo", "Comercial", "Compras", "Financeiro", "Operação", "Projetos"]


def get_usuarios():
    try:
        return [u.nome for u in Usuario.query.filter_by(ativo=True).order_by(Usuario.nome).all()]
    except Exception:
        return ConfigGerenciador.get("responsaveis", "Sedra").splitlines()


def get_areas():
    areas = ConfigGerenciador.get("areas", "\n".join(DEFAULT_AREAS)).splitlines()
    used = [a.area for a in AtividadeGerenciador.query.with_entities(AtividadeGerenciador.area).distinct() if a.area]
    return sorted(set(filter(None, areas + used)))


def registrar_historico(atividade_id, usuario_nome, descricao, tipo="acao"):
    h = HistoricoCard(
        atividade_id=atividade_id,
        usuario_nome=usuario_nome or "Sistema",
        tipo=tipo,
        descricao=descricao,
    )
    db.session.add(h)


# ── Rotas principais ───────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/relatorios")
def relatorios():
    return render_template("relatorios.html")


# ── API de dados iniciais ──────────────────────────────────────

@app.route("/api/dados")
def api_dados():
    atividades = AtividadeGerenciador.query.order_by(AtividadeGerenciador.criado_em.desc()).all()
    return jsonify({
        "ok": True,
        "tasks": [a.to_dict() for a in atividades],
        "settings": {"statuses": STATUSES, "priorities": PRIORITIES},
        "lists": {"areas": get_areas(), "responsaveis": get_usuarios()},
        "logoUrl": ConfigGerenciador.get("logo_url", ""),
    })


# ── API de atividades ──────────────────────────────────────────

@app.route("/api/atividade", methods=["POST"])
def api_salvar():
    data = request.get_json() or {}
    titulo = (data.get("titulo") or "").strip()
    if not titulo:
        return jsonify({"ok": False, "erro": "Informe o título da atividade."}), 400

    usuario = (data.get("usuarioAtual") or "Sistema").strip()
    ativ_id = (data.get("id") or "").strip()

    if ativ_id:
        ativ = AtividadeGerenciador.query.get(ativ_id)
        if not ativ:
            return jsonify({"ok": False, "erro": "Atividade não encontrada."}), 404
        eh_nova = False
    else:
        ativ = AtividadeGerenciador()
        db.session.add(ativ)
        eh_nova = True

    novo_status = data.get("status", "Em andamento")
    if novo_status not in STATUSES:
        novo_status = STATUSES[0]

    status_anterior = ativ.status if not eh_nova else None

    ativ.titulo      = titulo
    ativ.descricao   = (data.get("descricao") or "").strip()
    ativ.area        = (data.get("area") or "").strip()
    ativ.responsavel = (data.get("responsavel") or "").strip()
    ativ.prioridade  = data.get("prioridade", "Média") if data.get("prioridade") in PRIORITIES else "Média"
    ativ.prazo       = (data.get("prazo") or "")[:10]
    ativ.observacoes = (data.get("observacoes") or "").strip()
    ativ.links       = (data.get("links") or "").strip()
    ativ.atualizado_em = datetime.utcnow()

    # Timer
    if novo_status == "Em andamento" and ativ.status != "Em andamento":
        ativ.iniciar_timer()
    elif ativ.status == "Em andamento" and novo_status != "Em andamento":
        ativ.pausar_timer()

    ativ.status = novo_status

    if novo_status == "Concluído" and not ativ.concluido_em:
        ativ.concluido_em = datetime.utcnow()
    elif novo_status != "Concluído":
        ativ.concluido_em = None

    # Histórico automático
    if eh_nova:
        registrar_historico(ativ.id, usuario, f'Atividade criada com status "{novo_status}"')
    else:
        mudancas = []
        if status_anterior != novo_status:
            mudancas.append(f'Status: "{status_anterior}" → "{novo_status}"')
        if mudancas:
            registrar_historico(ativ.id, usuario, " | ".join(mudancas))

    db.session.commit()
    return jsonify({"ok": True, "task": ativ.to_dict()})


@app.route("/api/atividade/<ativ_id>/status", methods=["PUT"])
def api_status(ativ_id):
    ativ = AtividadeGerenciador.query.get(ativ_id)
    if not ativ:
        return jsonify({"ok": False, "erro": "Atividade não encontrada."}), 404

    data = request.get_json() or {}
    novo_status = data.get("status", "")
    usuario = (data.get("usuarioAtual") or "Sistema").strip()

    if novo_status not in STATUSES:
        return jsonify({"ok": False, "erro": "Status inválido."}), 400

    status_anterior = ativ.status

    if novo_status == "Em andamento" and ativ.status != "Em andamento":
        ativ.iniciar_timer()
    elif ativ.status == "Em andamento" and novo_status != "Em andamento":
        ativ.pausar_timer()

    ativ.status = novo_status
    ativ.atualizado_em = datetime.utcnow()

    if novo_status == "Concluído" and not ativ.concluido_em:
        ativ.concluido_em = datetime.utcnow()
    elif novo_status != "Concluído":
        ativ.concluido_em = None

    registrar_historico(ativ.id, usuario, f'Status: "{status_anterior}" → "{novo_status}"')

    db.session.commit()
    return jsonify({"ok": True, "task": ativ.to_dict()})


@app.route("/api/atividade/<ativ_id>", methods=["DELETE"])
def api_deletar(ativ_id):
    ativ = AtividadeGerenciador.query.get(ativ_id)
    if not ativ:
        return jsonify({"ok": False, "erro": "Atividade não encontrada."}), 404
    db.session.delete(ativ)
    db.session.commit()
    return jsonify({"ok": True})


# ── API de histórico e comentários ────────────────────────────

@app.route("/api/atividade/<ativ_id>/historico")
def api_historico(ativ_id):
    itens = HistoricoCard.query.filter_by(atividade_id=ativ_id).order_by(HistoricoCard.criado_em.desc()).all()
    return jsonify({"ok": True, "historico": [h.to_dict() for h in itens]})


@app.route("/api/atividade/<ativ_id>/comentario", methods=["POST"])
def api_comentario(ativ_id):
    ativ = AtividadeGerenciador.query.get(ativ_id)
    if not ativ:
        return jsonify({"ok": False, "erro": "Atividade não encontrada."}), 404

    data = request.get_json() or {}
    texto = (data.get("texto") or "").strip()
    usuario = (data.get("usuarioAtual") or "Sistema").strip()

    if not texto:
        return jsonify({"ok": False, "erro": "Comentário não pode ser vazio."}), 400

    registrar_historico(ativ_id, usuario, texto, tipo="comentario")
    db.session.commit()
    return jsonify({"ok": True})


# ── API de integração com SEDRA GUT ───────────────────────────

@app.route("/api/sedra-gut/importar", methods=["POST"])
def api_importar_sedra():
    """Recebe uma tarefa do SEDRA GUT e cria no Gerenciador com status Em andamento."""
    data = request.get_json() or {}
    sedra_id = (data.get("sedra_id") or "").strip()

    if sedra_id:
        existente = AtividadeGerenciador.query.filter_by(origem_sedra_id=sedra_id).first()
        if existente:
            return jsonify({"ok": True, "task": existente.to_dict(), "info": "ja_existe"})

    ativ = AtividadeGerenciador(
        titulo      = (data.get("titulo") or "Sem título").strip(),
        descricao   = (data.get("descricao") or "").strip(),
        area        = (data.get("categoria") or data.get("area") or "").strip(),
        responsavel = (data.get("responsavel") or "").strip(),
        status      = "Em andamento",
        prioridade  = "Alta" if (data.get("prioridade") or 0) >= 75 else "Média",
        prazo       = (data.get("prazo") or ""),
        origem_sedra_id = sedra_id,
    )
    ativ.iniciar_timer()
    db.session.add(ativ)
    registrar_historico(ativ.id, "SEDRA GUT", f'Importado do SEDRA GUT — prioridade GUT: {data.get("prioridade", "?")}')
    db.session.commit()

    return jsonify({"ok": True, "task": ativ.to_dict()})


# ── API de relatórios ──────────────────────────────────────────

@app.route("/api/relatorios")
def api_relatorios():
    atividades = AtividadeGerenciador.query.all()

    por_area = {}
    por_responsavel = {}
    por_prioridade = {}
    total_segundos = 0

    for a in atividades:
        tempo = a.tempo_segundos or 0
        total_segundos += tempo

        area = a.area or "Sem área"
        por_area[area] = por_area.get(area, 0) + tempo

        resp = a.responsavel or "Sem responsável"
        por_responsavel[resp] = por_responsavel.get(resp, 0) + tempo

        prio = a.prioridade or "Média"
        por_prioridade[prio] = por_prioridade.get(prio, 0) + tempo

    def fmt(segundos):
        h = segundos // 3600
        m = (segundos % 3600) // 60
        return f"{h}h {m:02d}m"

    return jsonify({
        "ok": True,
        "totalSegundos": total_segundos,
        "totalFormatado": fmt(total_segundos),
        "porArea": [{"area": k, "segundos": v, "formatado": fmt(v)} for k, v in sorted(por_area.items(), key=lambda x: -x[1])],
        "porResponsavel": [{"responsavel": k, "segundos": v, "formatado": fmt(v)} for k, v in sorted(por_responsavel.items(), key=lambda x: -x[1])],
        "porPrioridade": [{"prioridade": k, "segundos": v, "formatado": fmt(v)} for k, v in sorted(por_prioridade.items(), key=lambda x: -x[1])],
        "totalTarefas": len(atividades),
        "concluidas": sum(1 for a in atividades if a.status == "Concluído"),
        "emAndamento": sum(1 for a in atividades if a.status == "Em andamento"),
    })


@app.route("/api/listas", methods=["POST"])
def api_listas():
    data = request.get_json() or {}
    areas  = [a.strip() for a in (data.get("areas") or []) if a.strip()]
    logo   = (data.get("logoUrl") or "").strip()
    if areas:
        ConfigGerenciador.set("areas", "\n".join(sorted(set(areas))))
    if logo:
        ConfigGerenciador.set("logo_url", logo)
    return jsonify({"ok": True, "lists": {"areas": get_areas(), "responsaveis": get_usuarios()}, "logoUrl": ConfigGerenciador.get("logo_url", "")})


# ── Inicialização ──────────────────────────────────────────────
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    print("=" * 50)
    print("  SEDRA Gerenciador de Tarefas — V1.0")
    print("  Acesse: http://localhost:5001")
    print("=" * 50)
    app.run(debug=True, host="0.0.0.0", port=5001)
