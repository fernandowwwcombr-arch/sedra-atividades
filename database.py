from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()


def gerar_id():
    return str(uuid.uuid4())


# ── Tabela de usuários — compartilhada com SEDRA GUT ──────────
class Usuario(db.Model):
    __tablename__ = "usuarios"
    __table_args__ = {"extend_existing": True}

    id       = db.Column(db.Integer, primary_key=True)
    nome     = db.Column(db.String(100))
    email    = db.Column(db.String(120))
    perfil   = db.Column(db.String(20))
    ativo    = db.Column(db.Boolean, default=True)


# ── Atividades do Gerenciador ──────────────────────────────────
class AtividadeGerenciador(db.Model):
    __tablename__ = "gerenciador_atividades"

    id               = db.Column(db.String(36), primary_key=True, default=gerar_id)
    titulo           = db.Column(db.String(160), nullable=False)
    descricao        = db.Column(db.String(1200), default="")
    area             = db.Column(db.String(100), default="")
    responsavel      = db.Column(db.String(100), default="")
    status           = db.Column(db.String(50), default="Em andamento")
    prioridade       = db.Column(db.String(50), default="Media")
    prazo            = db.Column(db.String(10), default="")
    observacoes      = db.Column(db.String(1200), default="")
    links            = db.Column(db.Text, default="")

    # Rastreamento de tempo
    tempo_segundos   = db.Column(db.Integer, default=0)   # tempo acumulado
    ultimo_inicio    = db.Column(db.DateTime, nullable=True)  # início da sessão atual

    # Origem SEDRA GUT
    origem_sedra_id  = db.Column(db.String(36), nullable=True)

    criado_em        = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    concluido_em     = db.Column(db.DateTime, nullable=True)

    historico        = db.relationship("HistoricoCard", backref="atividade",
                                       cascade="all, delete-orphan",
                                       order_by="HistoricoCard.criado_em")

    def pausar_timer(self):
        """Acumula o tempo da sessão atual e limpa ultimo_inicio."""
        if self.ultimo_inicio:
            delta = (datetime.utcnow() - self.ultimo_inicio).total_seconds()
            self.tempo_segundos = (self.tempo_segundos or 0) + int(delta)
            self.ultimo_inicio = None

    def iniciar_timer(self):
        if not self.ultimo_inicio:
            self.ultimo_inicio = datetime.utcnow()

    def to_dict(self):
        return {
            "id":             self.id,
            "titulo":         self.titulo,
            "descricao":      self.descricao or "",
            "area":           self.area or "",
            "responsavel":    self.responsavel or "",
            "status":         self.status or "Em andamento",
            "prioridade":     self.prioridade or "Media",
            "prazo":          self.prazo or "",
            "observacoes":    self.observacoes or "",
            "links":          self.links or "",
            "tempoSegundos":  self.tempo_segundos or 0,
            "ultimoInicio":   self.ultimo_inicio.isoformat() if self.ultimo_inicio else None,
            "origemSedraId":  self.origem_sedra_id or "",
            "criadoEm":       self.criado_em.strftime("%Y-%m-%d") if self.criado_em else "",
            "atualizadoEm":   self.atualizado_em.strftime("%Y-%m-%d") if self.atualizado_em else "",
            "concluidoEm":    self.concluido_em.strftime("%Y-%m-%d") if self.concluido_em else "",
        }


# ── Histórico e comentários dos cards ─────────────────────────
class HistoricoCard(db.Model):
    __tablename__ = "gerenciador_historico"

    id           = db.Column(db.Integer, primary_key=True)
    atividade_id = db.Column(db.String(36), db.ForeignKey("gerenciador_atividades.id", ondelete="CASCADE"), nullable=False)
    usuario_nome = db.Column(db.String(100), default="Sistema")
    tipo         = db.Column(db.String(20), default="acao")   # "acao" ou "comentario"
    descricao    = db.Column(db.String(1000), nullable=False)
    criado_em    = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id":          self.id,
            "usuarioNome": self.usuario_nome,
            "tipo":        self.tipo,
            "descricao":   self.descricao,
            "criadoEm":    self.criado_em.strftime("%d/%m/%Y %H:%M") if self.criado_em else "",
        }


# ── Configurações do Gerenciador ──────────────────────────────
class ConfigGerenciador(db.Model):
    __tablename__ = "gerenciador_config"

    id    = db.Column(db.Integer, primary_key=True)
    chave = db.Column(db.String(50), unique=True, nullable=False)
    valor = db.Column(db.Text, default="")

    @staticmethod
    def get(chave, padrao=""):
        obj = ConfigGerenciador.query.filter_by(chave=chave).first()
        return obj.valor if obj else padrao

    @staticmethod
    def set(chave, valor):
        obj = ConfigGerenciador.query.filter_by(chave=chave).first()
        if obj:
            obj.valor = valor
        else:
            db.session.add(ConfigGerenciador(chave=chave, valor=valor))
        db.session.commit()
