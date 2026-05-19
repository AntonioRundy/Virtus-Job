"""
Seed script — populates the database with sample opportunities for development.
Run: docker compose exec api python -m app.scripts.seed
"""
import asyncio
import json
from datetime import date, timedelta

from sqlalchemy import text

from app.database import AsyncSessionLocal, Base, engine
from app.models import Opportunity, OpportunityCategory, Organization
from app.models.opportunity import Modality, OpportunityStatus, OpportunityType
from app.models.organization import OrgType
from app.services.opportunities import _make_slug
from app.services.trust_classifier import classifier as trust_classifier

SAMPLE_ORGS = [
    {
        "name": "Ministério da Educação",
        "slug": "ministerio-da-educacao",
        "type": OrgType.PUBLIC,
        "website": "https://med.gov.ao",
        "is_verified": True,
    },
    {
        "name": "Angola LNG",
        "slug": "angola-lng",
        "type": OrgType.PRIVATE,
        "website": "https://angolalng.com",
        "is_verified": True,
    },
    {
        "name": "Sonangol",
        "slug": "sonangol",
        "type": OrgType.PUBLIC,
        "website": "https://sonangol.co.ao",
        "is_verified": True,
    },
    {
        "name": "Unitel",
        "slug": "unitel",
        "type": OrgType.PRIVATE,
        "website": "https://unitel.co.ao",
        "is_verified": True,
    },
    {
        "name": "BAI — Banco Angolano de Investimentos",
        "slug": "bai",
        "type": OrgType.PRIVATE,
        "website": "https://bai.ao",
        "is_verified": True,
    },
    {
        "name": "TotalEnergies Angola",
        "slug": "totalenergies-angola",
        "type": OrgType.PRIVATE,
        "website": "https://totalenergies.com/angola",
        "is_verified": True,
    },
    {
        "name": "TAAG — Linhas Aéreas de Angola",
        "slug": "taag",
        "type": OrgType.PUBLIC,
        "website": "https://taag.com",
        "is_verified": True,
    },
    {
        "name": "Ministério das Finanças",
        "slug": "ministerio-das-financas",
        "type": OrgType.PUBLIC,
        "website": "https://minfin.gov.ao",
        "is_verified": True,
    },
    {
        "name": "Universidade Agostinho Neto",
        "slug": "uan",
        "type": OrgType.PUBLIC,
        "website": "https://uan.ao",
        "is_verified": True,
    },
    {
        "name": "BPC — Banco de Poupança e Crédito",
        "slug": "bpc",
        "type": OrgType.PUBLIC,
        "website": "https://bpc.ao",
        "is_verified": True,
    },
]

SAMPLE_OPPORTUNITIES = [
    {
        "title": "Concurso Público para Professor do Ensino Médio — Luanda",
        "type": OpportunityType.CONCURSO,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "O Ministério da Educação abre concurso público para recrutamento de professores "
            "do ensino médio nas disciplinas de Matemática, Física e Química para Luanda. "
            "Candidaturas presenciais nos serviços provinciais de educação."
        ),
        "requirements": json.dumps(
            ["Licenciatura em área relevante", "Experiência mínima de 2 anos", "Nacionalidade angolana"]
        ),
        "province": "Luanda",
        "source_url": "https://med.gov.ao",
        "source_name": "Ministério da Educação de Angola",
        "deadline": date.today() + timedelta(days=21),
        "application_type": "IN_PERSON",
        "org_slug": "ministerio-da-educacao",
        "categories": ["Educação", "Ensino", "Concurso Público"],
    },
    {
        "title": "Engenheiro de Processo Sénior — Setor Petrolífero",
        "type": OpportunityType.VAGA,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "Angola LNG procura Engenheiro de Processo Sénior com experiência em instalações "
            "de GNL para integrar a equipa de operações em Soyo, Zaire."
        ),
        "requirements": json.dumps(
            ["Licenciatura em Engenharia Química ou similar", "Mínimo 8 anos de experiência em GNL", "Inglês fluente"]
        ),
        "benefits": json.dumps(["Salário competitivo", "Seguro de saúde", "Alojamento"]),
        "province": "Zaire",
        "municipality": "Soyo",
        "salary_min": 800000.0,
        "salary_max": 1500000.0,
        "salary_currency": "AOA",
        "source_url": "https://www.angolalng.com",
        "source_name": "Angola LNG",
        "deadline": date.today() + timedelta(days=14),
        "application_type": "URL",
        "org_slug": "angola-lng",
        "categories": ["Engenharia", "Petróleo e Gás", "Sénior"],
    },
    {
        "title": "Bolsa de Estudos para Mestrado em Portugal — INAGBE 2026",
        "type": OpportunityType.BOLSA,
        "status": OpportunityStatus.ACTIVE,
        "modality": None,
        "description_structured": (
            "O INAGBE abre candidaturas para bolsas de estudos para mestrado em universidades "
            "portuguesas nas áreas de Engenharia, Medicina e Direito. "
            "Candidaturas submetidas por formulário online no portal do INAGBE."
        ),
        "requirements": json.dumps(
            ["Licenciatura com média superior a 14 valores", "Idade máxima 35 anos", "Cidadão angolano"]
        ),
        "province": "Luanda",
        "source_url": "https://inagbe.gov.ao",
        "source_name": "INAGBE — Instituto Nacional de Gestão de Bolsas de Estudo",
        "deadline": date.today() + timedelta(days=45),
        "application_type": "FORM",
        "contact_email": "bolsas@inagbe.gov.ao",
        "org_slug": None,
        "categories": ["Bolsa", "Mestrado", "Portugal", "Internacional"],
    },
    {
        "title": "Estágio Profissional em Tecnologias de Informação — Sonangol",
        "type": OpportunityType.ESTAGIO,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.HIBRIDO,
        "description_structured": (
            "A Sonangol abre programa de estágio profissional para recém-licenciados em "
            "Tecnologias de Informação, Sistemas de Informação e Engenharia Informática."
        ),
        "requirements": json.dumps(
            ["Licenciatura recente (máximo 2 anos)", "Conhecimentos de Python ou Java", "Disponibilidade imediata"]
        ),
        "province": "Luanda",
        "source_url": "https://sonangol.co.ao",
        "source_name": "Sonangol",
        "deadline": date.today() + timedelta(days=10),
        "application_type": "IN_PERSON",
        "org_slug": "sonangol",
        "categories": ["TI", "Estágio", "Tecnologia", "Informática"],
    },
    # ── Novas vagas adicionadas ──────────────────────────────────────────────────
    {
        "title": "Engenheiro de Redes e Telecomunicações Sénior — Unitel",
        "type": OpportunityType.VAGA,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "A Unitel, operadora líder de telecomunicações em Angola, recruta Engenheiro de Redes "
            "Sénior para gestão e optimização da infraestrutura de rede 4G/5G em Luanda. "
            "Responsável por planeamento de capacidade, resolução de incidentes e projetos de expansão."
        ),
        "requirements": json.dumps([
            "Licenciatura em Engenharia de Telecomunicações, Electrónica ou similar",
            "Mínimo 5 anos de experiência em redes móveis (GSM/LTE/5G)",
            "Certificação CCNP ou equivalente (preferencial)",
            "Inglês técnico fluente",
        ]),
        "benefits": json.dumps([
            "Seguro de saúde para o trabalhador e família",
            "Telemóvel corporativo com plano ilimitado",
            "Formação contínua certificada",
            "Subsídio de transporte",
        ]),
        "province": "Luanda",
        "salary_min": 450000.0,
        "salary_max": 750000.0,
        "salary_currency": "AOA",
        "source_url": "https://unitel.co.ao",
        "source_name": "Unitel",
        "deadline": date.today() + timedelta(days=18),
        "application_type": "URL",
        "org_slug": "unitel",
        "categories": ["Telecomunicações", "Engenharia", "TI", "Sénior"],
    },
    {
        "title": "Analista de Crédito Júnior — BAI",
        "type": OpportunityType.VAGA,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "O Banco Angolano de Investimentos (BAI) recruta Analista de Crédito Júnior para a "
            "Direcção de Crédito Empresarial. O candidato irá analisar propostas de crédito, "
            "avaliar risco de clientes corporate e elaborar pareceres de crédito."
        ),
        "requirements": json.dumps([
            "Licenciatura em Economia, Gestão, Finanças ou Contabilidade",
            "Conhecimentos de análise financeira e contabilidade",
            "Domínio de Excel e ferramentas de análise",
            "Até 2 anos de experiência (aceita recém-licenciados)",
        ]),
        "benefits": json.dumps([
            "Plano de carreira estruturado",
            "Formação interna e externa",
            "Seguro de saúde",
        ]),
        "province": "Luanda",
        "salary_min": 200000.0,
        "salary_max": 320000.0,
        "salary_currency": "AOA",
        "source_url": "https://bai.ao",
        "source_name": "BAI — Banco Angolano de Investimentos",
        "deadline": date.today() + timedelta(days=12),
        "application_type": "EMAIL",
        "contact_email": "recrutamento@bai.ao",
        "org_slug": "bai",
        "categories": ["Banca", "Finanças", "Crédito", "Júnior"],
    },
    {
        "title": "Geólogo de Reservatórios — TotalEnergies Angola",
        "type": OpportunityType.VAGA,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "A TotalEnergies Angola recruta Geólogo de Reservatórios para integrar a equipa de "
            "exploração no bloco 17, offshore Cabinda. Responsável por modelação de reservatórios, "
            "interpretação sísmica e integração de dados de poços."
        ),
        "requirements": json.dumps([
            "Mestrado ou Doutoramento em Geologia, Geofísica ou Engenharia de Petróleo",
            "Mínimo 6 anos de experiência em exploração offshore",
            "Domínio de software Petrel ou similar",
            "Inglês e Francês (preferencial)",
        ]),
        "benefits": json.dumps([
            "Pacote salarial competitivo internacional",
            "Alojamento e transporte para offshore",
            "Plano de pensões",
            "Seguro de saúde premium",
        ]),
        "province": "Cabinda",
        "salary_min": 1200000.0,
        "salary_max": 2000000.0,
        "salary_currency": "AOA",
        "source_url": "https://totalenergies.com",
        "source_name": "TotalEnergies Angola",
        "deadline": date.today() + timedelta(days=30),
        "application_type": "URL",
        "org_slug": "totalenergies-angola",
        "categories": ["Petróleo e Gás", "Geologia", "Engenharia", "Offshore"],
    },
    {
        "title": "Técnico de Manutenção Aeronáutica — TAAG",
        "type": OpportunityType.VAGA,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "A TAAG — Linhas Aéreas de Angola abre processo de recrutamento para Técnico de "
            "Manutenção Aeronáutica para a base de manutenção no Aeroporto Internacional "
            "de Luanda. Responsável por manutenção programada e não programada de aeronaves Boeing 737 e 777."
        ),
        "requirements": json.dumps([
            "Curso de Técnico de Manutenção Aeronáutica (AGNA/ANAC reconhecido)",
            "Licença PART-66 ou equivalente (preferencial)",
            "Experiência mínima de 3 anos em manutenção de aeronaves",
            "Disponibilidade para trabalho por turnos",
        ]),
        "benefits": json.dumps([
            "Benefícios em viagens aéreas",
            "Seguro de vida e saúde",
            "Subsídio de uniforme e alimentação",
        ]),
        "province": "Luanda",
        "salary_min": 350000.0,
        "salary_max": 550000.0,
        "salary_currency": "AOA",
        "source_url": "https://taag.com",
        "source_name": "TAAG — Linhas Aéreas de Angola",
        "deadline": date.today() + timedelta(days=25),
        "application_type": "IN_PERSON",
        "org_slug": "taag",
        "categories": ["Aviação", "Manutenção", "Aeronáutica", "Técnico"],
    },
    {
        "title": "Concurso Público para Técnico Superior de Auditoria — Ministério das Finanças",
        "type": OpportunityType.CONCURSO,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "O Ministério das Finanças abre concurso público para provimento de 20 vagas de "
            "Técnico Superior de Auditoria na Inspecção-Geral das Finanças. "
            "Os candidatos aprovados serão integrados no quadro de pessoal efectivo do Ministério."
        ),
        "requirements": json.dumps([
            "Licenciatura em Contabilidade, Finanças, Economia ou Auditoria",
            "Média de licenciatura igual ou superior a 14 valores",
            "Cidadania angolana",
            "Idade não superior a 35 anos à data de candidatura",
        ]),
        "province": "Luanda",
        "source_url": "https://minfin.gov.ao",
        "source_name": "Ministério das Finanças de Angola",
        "deadline": date.today() + timedelta(days=35),
        "application_type": "IN_PERSON",
        "org_slug": "ministerio-das-financas",
        "categories": ["Finanças", "Auditoria", "Governo", "Concurso Público"],
    },
    {
        "title": "Bolsa de Doutoramento em Engenharia Biomédica — INAGBE 2026",
        "type": OpportunityType.BOLSA,
        "status": OpportunityStatus.ACTIVE,
        "modality": None,
        "description_structured": (
            "O INAGBE disponibiliza bolsas de doutoramento em Engenharia Biomédica e Ciências da "
            "Saúde em parceria com universidades de Portugal, Brasil e Espanha. "
            "As bolsas incluem propinas, subsídio mensal de vida e passagem aérea."
        ),
        "requirements": json.dumps([
            "Mestrado concluído com média superior a 16 valores",
            "Pré-projecto de investigação aprovado por uma universidade parceira",
            "Idade máxima 40 anos",
            "Cidadania angolana",
        ]),
        "province": "Luanda",
        "source_url": "https://inagbe.gov.ao",
        "source_name": "INAGBE — Instituto Nacional de Gestão de Bolsas de Estudo",
        "deadline": date.today() + timedelta(days=60),
        "application_type": "FORM",
        "contact_email": "doutoramentos@inagbe.gov.ao",
        "org_slug": None,
        "categories": ["Bolsa", "Doutoramento", "Saúde", "Internacional"],
    },
    {
        "title": "Formação em Gestão de Projectos (PMP) — UAN",
        "type": OpportunityType.FORMACAO,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "A Universidade Agostinho Neto, através do Centro de Formação Contínua, oferece "
            "programa de formação em Gestão de Projectos com preparação para a certificação PMP "
            "(Project Management Professional). Duração: 120 horas, regime pós-laboral."
        ),
        "requirements": json.dumps([
            "Licenciatura em qualquer área",
            "Experiência profissional mínima de 2 anos",
            "Disponibilidade pós-laboral (18h-21h)",
        ]),
        "benefits": json.dumps([
            "Certificado da UAN reconhecido pelo Estado angolano",
            "Preparação para exame PMP internacional",
            "Material didáctico incluído",
        ]),
        "province": "Luanda",
        "salary_min": None,
        "salary_max": None,
        "source_url": "https://uan.ao",
        "source_name": "Universidade Agostinho Neto",
        "deadline": date.today() + timedelta(days=15),
        "application_type": "IN_PERSON",
        "org_slug": "uan",
        "categories": ["Formação", "Gestão de Projectos", "PMP", "Certificação"],
    },
    {
        "title": "Estágio em Desenvolvimento de Software — Huawei Technologies Angola",
        "type": OpportunityType.ESTAGIO,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.HIBRIDO,
        "description_structured": (
            "A Huawei Technologies Angola abre programa de estágio Seeds for the Future para "
            "estudantes e recém-licenciados em Engenharia Informática e áreas STEM. "
            "Estágio de 6 meses com possibilidade de integração directa na empresa."
        ),
        "requirements": json.dumps([
            "Estudante finalista ou recém-licenciado em Eng. Informática, TI ou STEM",
            "Média académica igual ou superior a 14 valores",
            "Conhecimentos de programação (Python, Java ou C++)",
            "Inglês intermédio (mínimo B1)",
        ]),
        "benefits": json.dumps([
            "Bolsa mensal de estágio",
            "Mentoria com especialistas internacionais",
            "Formação em tecnologias Huawei (certificações incluídas)",
            "Possibilidade de visita à sede em Shenzhen",
        ]),
        "province": "Luanda",
        "source_url": "https://huawei.com/ao",
        "source_name": "Huawei Technologies Angola",
        "deadline": date.today() + timedelta(days=20),
        "application_type": "URL",
        "org_slug": None,
        "categories": ["TI", "Estágio", "Desenvolvimento de Software", "Tecnologia"],
    },
    {
        "title": "Técnico de Segurança Industrial — Sonangol Distribuidora",
        "type": OpportunityType.VAGA,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "A Sonangol Distribuidora recruta Técnico de Segurança Industrial para a zona de "
            "Benguela/Lobito. Responsável por implementar planos de HSE, realizar auditorias "
            "de segurança e coordenar simulacros e formações."
        ),
        "requirements": json.dumps([
            "Licenciatura em Segurança Industrial, Engenharia do Ambiente ou similar",
            "Certificação em HSE (NEBOSH, IOSH ou equivalente)",
            "Mínimo 3 anos de experiência em ambiente industrial",
            "Carta de condução válida",
        ]),
        "benefits": json.dumps([
            "Seguro de saúde e de vida",
            "Subsídio de deslocação",
            "Equipamento de protecção individual fornecido",
        ]),
        "province": "Benguela",
        "municipality": "Lobito",
        "salary_min": 280000.0,
        "salary_max": 420000.0,
        "salary_currency": "AOA",
        "source_url": "https://sonangol.co.ao",
        "source_name": "Sonangol",
        "deadline": date.today() + timedelta(days=22),
        "application_type": "EMAIL",
        "contact_email": "rh.distribuidora@sonangol.co.ao",
        "org_slug": "sonangol",
        "categories": ["Segurança Industrial", "HSE", "Petróleo e Gás", "Benguela"],
    },
    {
        "title": "Analista de Risco de Crédito — BPC",
        "type": OpportunityType.VAGA,
        "status": OpportunityStatus.ACTIVE,
        "modality": Modality.PRESENCIAL,
        "description_structured": (
            "O Banco de Poupança e Crédito (BPC) recruta Analista de Risco de Crédito para "
            "a Direcção de Gestão de Risco. Responsável por desenvolver modelos de scoring, "
            "monitorizar a carteira de crédito e elaborar relatórios de risco para o BNA."
        ),
        "requirements": json.dumps([
            "Licenciatura em Matemática, Estatística, Economia ou Engenharia",
            "Experiência mínima de 2 anos em análise de risco bancário",
            "Domínio de Python ou R para análise de dados",
            "Conhecimento da regulamentação BNA",
        ]),
        "benefits": json.dumps([
            "Plano de saúde abrangente",
            "Formação contínua subsidiada",
            "13.º e 14.º mês garantidos",
        ]),
        "province": "Luanda",
        "salary_min": 300000.0,
        "salary_max": 500000.0,
        "salary_currency": "AOA",
        "source_url": "https://bpc.ao",
        "source_name": "BPC — Banco de Poupança e Crédito",
        "deadline": date.today() + timedelta(days=17),
        "application_type": "EMAIL",
        "contact_email": "recrutamento@bpc.ao",
        "org_slug": "bpc",
        "categories": ["Banca", "Risco de Crédito", "Finanças", "Análise de Dados"],
    },
]

DB_FIELDS = {
    "title", "type", "status", "modality", "description_structured",
    "requirements", "benefits", "tags", "province", "municipality",
    "salary_min", "salary_max", "salary_currency", "source_url",
    "source_name", "deadline", "contact_email", "application_url",
    "document_url", "application_type",
}


async def seed() -> None:
    print("Creating tables if not exist...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        # Create organizations
        org_map: dict[str, Organization] = {}
        for org_data in SAMPLE_ORGS:
            org = Organization(**org_data)
            db.add(org)
            await db.flush()
            org_map[org.slug] = org
            print(f"  Created org: {org.name}")

        # Create opportunities — work on copies to avoid mutating module-level data
        for raw in SAMPLE_OPPORTUNITIES:
            data = dict(raw)
            cats: list[str] = data.pop("categories", [])
            org_slug: str | None = data.pop("org_slug", None)

            # Keep only fields that exist on the ORM model
            opp_kwargs = {k: v for k, v in data.items() if k in DB_FIELDS}

            # Compute trust from source_url domain
            source_url = data["source_url"]
            trust_level = trust_classifier.classify_url(source_url)
            trust_score = trust_classifier.trust_score(source_url)

            opp = Opportunity(
                slug=_make_slug(data["title"], data["type"].value),
                organization_id=org_map[org_slug].id if org_slug and org_slug in org_map else None,
                trust_level=trust_level.value,
                trust_score=trust_score,
                **opp_kwargs,
            )
            db.add(opp)
            await db.flush()

            for cat in cats:
                db.add(OpportunityCategory(opportunity_id=opp.id, category=cat))

            print(f"  Created: {opp.title[:70]}")

        await db.commit()

    print("\nSeed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
