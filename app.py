from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
import os


app = Flask(__name__)
app.secret_key = 'chave_secreta_cantina'

#lista fixa de comorbidades que aparecem no forms do aluno
LISTA_COMORBIDADES = ['Diabetes', 'Intolerancia a Lactose', 'Alergia a Amendoim', 'Doenca Celiaca', 'Hipertensao']


# conexao com o bd: tudo vem das variaveis de ambiente (Render ou PowerShell local)
# nenhuma senha fica escrita no codigo. Os padroes abaixo servem so pro MySQL do seu PC
def conectar_bd():
    return mysql.connector.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 3306)),
        user=os.environ.get('DB_USER', 'root'),
        password=os.environ.get('DB_PASSWORD', ''),
        database=os.environ.get('DB_NAME', 'cantina'),
        #na nuvem (Aiven) o SSL fica ligado; se o MySQL local reclamar de SSL, defina DB_SSL_DISABLED=1
        ssl_disabled=os.environ.get('DB_SSL_DISABLED', '0') == '1',
        charset='utf8mb4',
        collation='utf8mb4_unicode_ci')



def calcular_percentual(lista, chave):
    #pra calcular a largura % de cada barra do gráfico com base no maior valor da lista
    maior_valor = max([item[chave] for item in lista], default=0) or 1
    for item in lista:
        item['percentual'] = int((item[chave] / maior_valor) * 100)
    return lista



#1. rota da pág inicial
@app.route('/')
def home():
    cardapio = []
    avisos = []
    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("select * from cardapio")
        cardapio = cursor.fetchall()

        cursor.execute("select * from avisos where ativo = 1 order by id_aviso desc")
        avisos = cursor.fetchall()

        cursor.close()
        conexao.close()
    except Exception as e:
        print(e)

    return render_template('index.html', cardapio=cardapio, avisos=avisos)



#2. rota de cadastro alunos
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if request.method == 'POST':
        nome = request.form['nome']
        matricula = request.form['matricula']
        senha = request.form['senha']
        turma = request.form.get('turma', 'Nao informada')

        try:
            conexao = conectar_bd()
            cursor = conexao.cursor()
            cursor.execute(
                "insert into alunos (nome, matricula, senha, turma, status_cadastro) values (%s, %s, %s, %s, 'ativo')",
                (nome, matricula, senha, turma)
            )
            conexao.commit()
            cursor.close()
            conexao.close()
            flash('Cadastro realizado com sucesso. Faça login.', 'sucesso')
            return redirect(url_for('home'))
        except Exception as e:
            print(e)
            flash('Erro ao cadastrar. Matrícula já existe.', 'erro')
            return redirect(url_for('cadastro'))

    return render_template('cadastro.html')



#3. rota de login do aluno
@app.route('/login', methods=['POST'])
def login():
    matricula = request.form['matricula']
    senha = request.form['senha']

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("select * from alunos where matricula = %s and senha = %s", (matricula, senha))
        aluno = cursor.fetchone()
        cursor.close()
        conexao.close()

        if aluno and (aluno['status_cadastro'] or '').lower() != 'ativo':
            #cadastro desativado pelo admin: nao deixa entrar
            flash('Seu cadastro está inativo. Procure a secretaria.', 'erro')
            return redirect(url_for('home'))

        if aluno:
            session['id_aluno'] = aluno['id_aluno']
            session['nome_aluno'] = aluno['nome']
            return redirect(url_for('painel_aluno'))

        flash('Matrícula ou senha incorretos', 'erro')
    except Exception as e:
        print(e)
        flash('Erro ao tentar fazer login.', 'erro')

    return redirect(url_for('home'))



#4. rota de login administrativo - admin e nutri
@app.route('/login_admin', methods=['GET', 'POST'])
def login_admin():
    if request.method == 'POST':
        login_usuario = request.form['login']
        senha = request.form['senha']

        if login_usuario == 'admin' and senha == 'admin123':
            session['id_usuario'] = 1
            session['perfil'] = 'admin'
            return redirect(url_for('painel_admin'))
        elif login_usuario == 'nutri' and senha == 'nutri123':
            session['id_usuario'] = 2
            session['perfil'] = 'nutricionista'
            return redirect(url_for('painel_nutricionista'))
        else:
            flash('Usuário ou senha incorretos!', 'erro')

    return render_template('login_admin.html')



#5. rota do painel do aluno - cardapio, agendamentos e ficha de saúde)
@app.route('/painel_aluno')
def painel_aluno():
    if 'id_aluno' not in session:
        return redirect(url_for('home'))

    id_aluno = session['id_aluno']
    cardapio_semana = []
    agendamentos = []
    avisos = []
    comorbidades_salvas = ''
    atestado_texto = ''

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("select * from cardapio")
        cardapio_semana = cursor.fetchall()

        cursor.execute("""
            select ag.id_grid_reserva, ag.data_reserva, ag.status_reserva,
                   c.dia_semana, c.refeicao_principal
            from agendamentos ag
            join cardapio c on ag.id_cardapio = c.id_cardapio
            where ag.id_aluno = %s
            order by ag.data_reserva desc
        """, (id_aluno,))
        agendamentos = cursor.fetchall()

        cursor.execute("select * from avisos where ativo = 1 order by id_aviso desc")
        avisos = cursor.fetchall()

        cursor.execute("select comorbidades, atestado_arquivo from alunos where id_aluno = %s", (id_aluno,))
        ficha = cursor.fetchone()
        if ficha:
            comorbidades_salvas = ficha['comorbidades'] or ''
            atestado_texto = ficha['atestado_arquivo'] or ''

        cursor.close()
        conexao.close()
    except Exception as e:
        print(e)

    #compara em minusculas para marcar certo o checkbox, mesmo se o banco salvou diferente
    salvas_lower = [item.strip().lower() for item in comorbidades_salvas.split(',') if item.strip()]
    marcadas = [opcao for opcao in LISTA_COMORBIDADES if opcao.lower() in salvas_lower]

    return render_template('painel_aluno.html', cardapio_semana=cardapio_semana, agendamentos=agendamentos,
avisos=avisos, lista_comorbidades=LISTA_COMORBIDADES, marcadas=marcadas, atestado_texto=atestado_texto)



#6. rota p/ salvar as comorbidades e atestado do aluno
@app.route('/salvar_saude', methods=['POST'])
def salvar_saude():
    if 'id_aluno' not in session:
        return redirect(url_for('home'))

    comorbidades_lista = request.form.getlist('comorbidades')
    comorbidades_str = ', '.join(comorbidades_lista)

    #captura o nome do arquivo enviado sem guardar ele
    arquivo = request.files.get('atestado_arquivo')
    nome_arquivo = arquivo.filename if arquivo and arquivo.filename else ''

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()

        if nome_arquivo:
            #aluno escolheu um arquivo novo: atualiza o nome salvo
            cursor.execute(
                "update alunos set comorbidades = %s, atestado_arquivo = %s where id_aluno = %s",
                (comorbidades_str, nome_arquivo, session['id_aluno'])
            )
        else:
            #nenhum arquivo novo selecionado: mantém o nome que ja estava salvo
            cursor.execute(
                "update alunos set comorbidades = %s where id_aluno = %s",
                (comorbidades_str, session['id_aluno'])
            )

        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Dados de saúde atualizados com sucesso!', 'sucesso')
    except Exception as e:
        print(e)
        flash('Erro ao salvar os dados de saúde.', 'erro')

    return redirect(url_for('painel_aluno'))



# 7. rota p criar um agendamento de refeição (link <a href> e faz GET)
@app.route('/agendar/<int:id_cardapio>')
def agendar(id_cardapio):
    if 'id_aluno' not in session:
        return redirect(url_for('home'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute(
            "insert into agendamentos (id_aluno, id_cardapio) values (%s, %s)",
            (session['id_aluno'], id_cardapio)
        )
        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Refeição agendada com sucesso!', 'sucesso')
    except Exception as e:
        print(e)
        flash('Não foi possível agendar agora. Tente novamente.', 'erro')

    return redirect(url_for('painel_aluno'))


#7.1 rota p cancelar um agendamento
@app.route('/cancelar_agendamento/<int:id_reserva>', methods=['POST'])
def cancelar_agendamento(id_reserva):
    if 'id_aluno' not in session:
        return redirect(url_for('home'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        #so apaga se o agendamento for do proprio aluno logado
        cursor.execute(
            "delete from agendamentos where id_grid_reserva = %s and id_aluno = %s",
            (id_reserva, session['id_aluno'])
        )
        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Agendamento cancelado com sucesso!', 'sucesso')
    except Exception as e:
        print(e)
        flash('Nao foi possível cancelar agora. Tente novamente.', 'erro')

    return redirect(url_for('painel_aluno'))



#8. rota do painel do admin - alunos, estoque e estatísticas
@app.route('/painel_admin')
def painel_admin():
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    alunos = []
    estoque = []
    agendamentos = []
    avisos = []
    cardapio = []
    relatorio_agend = []
    total_alunos = 0
    total_agendamentos = 0

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("select * from alunos order by nome")
        alunos = cursor.fetchall()

        cursor.execute("select count(*) as total from alunos")
        total_alunos = cursor.fetchone()['total']

        cursor.execute("select count(*) as total from agendamentos")
        total_agendamentos = cursor.fetchone()['total']

        cursor.execute("select * from estoque order by nome_item")
        estoque = cursor.fetchall()

        #todos os agendamentos, com nome do aluno e do prato, pra aba de agendamentos
        cursor.execute("""
            select ag.id_grid_reserva, ag.data_reserva, ag.status_reserva,
                   a.nome, a.turma, c.dia_semana, c.refeicao_principal
            from agendamentos ag
            join alunos a on ag.id_aluno = a.id_aluno
            join cardapio c on ag.id_cardapio = c.id_cardapio
            order by ag.data_reserva desc, ag.id_grid_reserva desc
        """)
        agendamentos = cursor.fetchall()

        #todos os avisos (publicados e ocultos), os mais novos primeiro
        cursor.execute("select * from avisos order by id_aviso desc")
        avisos = cursor.fetchall()

        #cardapio da semana, na ordem de segunda a sexta
        cursor.execute("select * from cardapio order by id_cardapio")
        cardapio = cursor.fetchall()

        cursor.execute("""
            select c.dia_semana, count(ag.id_grid_reserva) as total_agendamentos
            from cardapio c
            left join agendamentos ag on c.id_cardapio = ag.id_cardapio
            group by c.dia_semana, c.id_cardapio
            order by c.id_cardapio
        """)
        relatorio_agend = cursor.fetchall()
        relatorio_agend = calcular_percentual(relatorio_agend, 'total_agendamentos')

        cursor.close()
        conexao.close()
    except Exception as e:
        print(e)

    return render_template(
    'painel_admin.html', alunos=alunos, estoque=estoque, total_alunos=total_alunos, 
    total_agendamentos=total_agendamentos, total_itens_estoque=len(estoque), relatorio_agend=relatorio_agend,
    agendamentos=agendamentos, avisos=avisos, cardapio=cardapio)


#8.1 rota p o admin cancelar o agendamento de qualquer aluno
@app.route('/admin/cancelar_agendamento/<int:id_reserva>', methods=['POST'])
def admin_cancelar_agendamento(id_reserva):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute("delete from agendamentos where id_grid_reserva = %s", (id_reserva,))
        apagados = cursor.rowcount
        conexao.commit()
        cursor.close()
        conexao.close()
        if apagados:
            flash('Agendamento cancelado.', 'sucesso')
        else:
            flash('Esse agendamento já não existe.', 'erro')
    except Exception as e:
        print(e)
        flash('Erro ao cancelar o agendamento.', 'erro')

    return redirect(url_for('painel_admin', _anchor='agendamentos'))



#8.2 rota p cadastrar um aviso (ja nasce publicado)
ICONES_AVISO = ['bell', 'star', 'info', 'leaf', 'clock']

@app.route('/avisos/cadastrar', methods=['POST'])
def cadastrar_aviso():
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    titulo = request.form.get('titulo', '').strip()[:100]
    conteudo = request.form.get('conteudo', '').strip()[:500]
    icone = request.form.get('tipo_icone', 'bell')
    if icone not in ICONES_AVISO:
        icone = 'bell'

    if not titulo or not conteudo:
        flash('Preencha o título e o texto do aviso.', 'erro')
        return redirect(url_for('painel_admin', _anchor='avisos'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute(
            "insert into avisos (titulo, conteudo, tipo_icone, ativo) values (%s, %s, %s, 1)",
            (titulo, conteudo, icone)
        )
        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Aviso publicado com sucesso.', 'sucesso')
    except Exception as e:
        print(e)
        flash('Erro ao publicar o aviso.', 'erro')

    return redirect(url_for('painel_admin', _anchor='avisos'))


#8.3 rota p publicar/ocultar um aviso (alterna o campo ativo)
@app.route('/avisos/alternar/<int:id_aviso>', methods=['POST'])
def alternar_aviso(id_aviso):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute("update avisos set ativo = if(ativo = 1, 0, 1) where id_aviso = %s", (id_aviso,))
        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Situação do aviso atualizada.', 'sucesso')
    except Exception as e:
        print(e)
        flash('Erro ao atualizar o aviso.', 'erro')

    return redirect(url_for('painel_admin', _anchor='avisos'))


#8.4 rota p excluir um aviso
@app.route('/avisos/excluir/<int:id_aviso>', methods=['POST'])
def excluir_aviso(id_aviso):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute("delete from avisos where id_aviso = %s", (id_aviso,))
        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Aviso excluído.', 'sucesso')
    except Exception as e:
        print(e)
        flash('Erro ao excluir o aviso.', 'erro')

    return redirect(url_for('painel_admin', _anchor='avisos'))


#8.5 rota p editar o cardapio de um dia (GET mostra o formulario, POST salva)
#o dia da semana nao muda: as fotos e o valor nutricional da tela do aluno sao ligados a ele
EMOJIS_SOBREMESA = [
    ('🍌', 'Banana'), ('🍊', 'Laranja'), ('🍎', 'Maçã'), ('🍈', 'Melão'), ('🍮', 'Gelatina'),
    ('🍇', 'Uva'), ('🍉', 'Melancia'), ('🍓', 'Morango'), ('🍍', 'Abacaxi'), ('🍐', 'Pera'),
    ('🍑', 'Pêssego'), ('🥭', 'Manga'), ('🍰', 'Bolo'), ('🍨', 'Sorvete')
]

@app.route('/cardapio/editar/<int:id_cardapio>', methods=['GET', 'POST'])
def editar_cardapio(id_cardapio):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        refeicao = request.form.get('refeicao_principal', '').strip()[:80]
        acompanhamentos = request.form.get('acompanhamentos', '').strip()[:60]
        emoji = request.form.get('emoji', '').strip()
        nome_sobremesa = request.form.get('nome_sobremesa', '').strip()[:50]

        if not refeicao:
            flash('Informe a refeição principal.', 'erro')
            return redirect(url_for('editar_cardapio', id_cardapio=id_cardapio))
        if ' ' in emoji or len(emoji) > 8:
            flash('Escolha um emoji válido para a sobremesa.', 'erro')
            return redirect(url_for('editar_cardapio', id_cardapio=id_cardapio))

        #formato guardado no banco: "emoji + espaço + nome" (a Home separa pelo primeiro espaço)
        sobremesa = (emoji + ' ' + nome_sobremesa) if (emoji and nome_sobremesa) else ''

        try:
            conexao = conectar_bd()
            cursor = conexao.cursor()
            cursor.execute("""
                update cardapio
                set refeicao_principal = %s, acompanhamentos = %s, fruta_sobremesa = %s
                where id_cardapio = %s
            """, (refeicao, acompanhamentos, sobremesa, id_cardapio))
            conexao.commit()
            cursor.close()
            conexao.close()
            flash('Cardápio atualizado com sucesso.', 'sucesso')
            return redirect(url_for('painel_admin', _anchor='cardapio'))
        except Exception as e:
            print(e)
            flash('Erro ao atualizar o cardápio.', 'erro')
            return redirect(url_for('editar_cardapio', id_cardapio=id_cardapio))

    #GET: busca o dia pra preencher o formulario
    item = None
    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("select * from cardapio where id_cardapio = %s", (id_cardapio,))
        item = cursor.fetchone()
        cursor.close()
        conexao.close()
    except Exception as e:
        print(e)

    if not item:
        flash('Dia do cardápio não encontrado.', 'erro')
        return redirect(url_for('painel_admin', _anchor='cardapio'))

    #separa "emoji nome" nas duas partes do formulario
    partes = (item['fruta_sobremesa'] or '').split(' ', 1)
    if len(partes) == 2:
        emoji_atual, nome_atual = partes
    elif partes[0] and partes[0].isascii():
        emoji_atual, nome_atual = '', partes[0]
    else:
        emoji_atual, nome_atual = partes[0], ''

    #se o emoji salvo nao esta na lista, ele entra como primeira opcao pra nao se perder
    opcoes_emoji = list(EMOJIS_SOBREMESA)
    if emoji_atual and emoji_atual not in [e for e, _ in opcoes_emoji]:
        opcoes_emoji.insert(0, (emoji_atual, ''))

    return render_template('editar_cardapio.html', item=item, opcoes_emoji=opcoes_emoji,
                           emoji_atual=emoji_atual, nome_atual=nome_atual)


#8.6 rota p editar os dados de um aluno (GET mostra o formulario, POST salva)
LISTA_TURMAS = ['1º ANO A', '1º ANO B', '1º ANO C', '2º ANO A', '2º ANO B', '2º ANO C',
                '3º ANO A', '3º ANO B', '3º ANO C']

@app.route('/alunos/editar/<int:id_aluno>', methods=['GET', 'POST'])
def editar_aluno(id_aluno):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()[:80]
        matricula = request.form.get('matricula', '').strip()[:12]
        senha = request.form.get('senha', '').strip()[:12]
        turma = request.form.get('turma', '').strip()[:20]
        status = request.form.get('status_cadastro', '')

        if not nome or not matricula or not turma:
            flash('Preencha nome, matrícula e turma.', 'erro')
            return redirect(url_for('editar_aluno', id_aluno=id_aluno))
        if status not in ('ativo', 'inativo'):
            flash('Escolha uma situação válida para o cadastro.', 'erro')
            return redirect(url_for('editar_aluno', id_aluno=id_aluno))

        try:
            conexao = conectar_bd()
            cursor = conexao.cursor()

            if senha:
                #senha preenchida: troca a senha do aluno
                cursor.execute("""
                    update alunos
                    set nome = %s, matricula = %s, turma = %s, status_cadastro = %s, senha = %s
                    where id_aluno = %s
                """, (nome, matricula, turma, status, senha, id_aluno))
            else:
                #senha em branco: mantem a senha que ja estava salva
                cursor.execute("""
                    update alunos
                    set nome = %s, matricula = %s, turma = %s, status_cadastro = %s
                    where id_aluno = %s
                """, (nome, matricula, turma, status, id_aluno))

            conexao.commit()
            cursor.close()
            conexao.close()
            flash('Aluno atualizado com sucesso.', 'sucesso')
            return redirect(url_for('painel_admin', _anchor='alunos'))
        except mysql.connector.IntegrityError:
            #matricula e unica no banco
            flash('Já existe outro aluno com essa matrícula.', 'erro')
            return redirect(url_for('editar_aluno', id_aluno=id_aluno))
        except Exception as e:
            print(e)
            flash('Erro ao atualizar o aluno.', 'erro')
            return redirect(url_for('editar_aluno', id_aluno=id_aluno))

    #GET: busca o aluno pra preencher o formulario
    aluno = None
    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("select * from alunos where id_aluno = %s", (id_aluno,))
        aluno = cursor.fetchone()
        cursor.close()
        conexao.close()
    except Exception as e:
        print(e)

    if not aluno:
        flash('Aluno não encontrado.', 'erro')
        return redirect(url_for('painel_admin', _anchor='alunos'))

    #se a turma salva nao esta na lista (ex.: 'Não informada'), ela entra como primeira opcao
    turmas = list(LISTA_TURMAS)
    if aluno['turma'] and aluno['turma'] not in turmas:
        turmas.insert(0, aluno['turma'])

    status_atual = 'ativo' if (aluno['status_cadastro'] or '').lower() == 'ativo' else 'inativo'
    return render_template('editar_aluno.html', aluno=aluno, turmas=turmas, status_atual=status_atual)


#8.7 rota p excluir um aluno (os agendamentos dele sao apagados junto pelo banco - on delete cascade)
@app.route('/alunos/excluir/<int:id_aluno>', methods=['POST'])
def excluir_aluno(id_aluno):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute("delete from alunos where id_aluno = %s", (id_aluno,))
        apagados = cursor.rowcount
        conexao.commit()
        cursor.close()
        conexao.close()
        if apagados:
            flash('Aluno excluído.', 'sucesso')
        else:
            flash('Esse aluno já não existe.', 'erro')
    except Exception as e:
        print(e)
        flash('Erro ao excluir o aluno.', 'erro')

    return redirect(url_for('painel_admin', _anchor='alunos'))


#9. rota do painel da nutri - relatório de saúde e estatisticas
@app.route('/painel_nutricionista')
def painel_nutricionista():
    if session.get('perfil') != 'nutricionista':
        return redirect(url_for('login_admin'))

    ficha_saude = []
    relatorio_agend = []
    total_alunos = 0
    total_agendamentos = 0

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)

        cursor.execute("select count(*) as total from alunos")
        total_alunos = cursor.fetchone()['total']

        cursor.execute("select count(*) as total from agendamentos")
        total_agendamentos = cursor.fetchone()['total']

        cursor.execute("""
            select c.dia_semana, count(ag.id_grid_reserva) as total_agendamentos
            from cardapio c
            left join agendamentos ag on c.id_cardapio = ag.id_cardapio
            group by c.dia_semana, c.id_cardapio
            order by c.id_cardapio
        """)
        relatorio_agend = cursor.fetchall()
        relatorio_agend = calcular_percentual(relatorio_agend, 'total_agendamentos')

        cursor.execute("""
            select nome, turma, comorbidades, atestado_arquivo
            from alunos
            where comorbidades != '' or atestado_arquivo != ''
            order by nome""")
        ficha_saude = cursor.fetchall()

        cursor.close()
        conexao.close()
    except Exception as e:
        print(e)

    return render_template('painel_nutricionista.html', ficha_saude=ficha_saude, relatorio_agend=relatorio_agend,
    total_alunos=total_alunos, total_agendamentos=total_agendamentos)


#10. rota de redirecionamento do card estoque
@app.route('/estoque')
def estoque():
    return redirect(url_for('painel_admin'))


#10.1 rota p cadastrar um novo item de estoque
@app.route('/estoque/cadastrar', methods=['POST'])
def cadastrar_estoque():
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    nome_item = request.form['nome_item']
    quantidade = request.form['quantidade_disponivel']
    unidade = request.form.get('unidade_medida', 'unidade')
    data_entrada = request.form.get('data_entrada') or None
    data_validade = request.form.get('data_validade') or None
    perecivel = 1 if request.form.get('perecivel') == 'sim' else 0

    #valida quantidade - não permite 0 ou negativo
    try:
        quantidade_num = int(quantidade)
    except (ValueError, TypeError):
        quantidade_num = 0

    if quantidade_num < 1:
        flash('A quantidade precisa ser de no mínimo 1 para cadastrar o item.', 'erro')
        return redirect(url_for('painel_admin', _anchor='estoque'))

    #captura o nome do arquivo da nota fiscal enviado, sem guardar ele fisicamente
    arquivo_nf = request.files.get('nota_fiscal')
    nota_fiscal = arquivo_nf.filename if arquivo_nf and arquivo_nf.filename else ''

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute("""
            insert into estoque
                (nome_item, quantidade_disponivel, unidade_medida, data_entrada, data_validade, nota_fiscal, perecivel)
            values (%s, %s, %s, %s, %s, %s, %s)
        """, (nome_item, quantidade_num, unidade, data_entrada, data_validade, nota_fiscal, perecivel))
        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Item cadastrado no estoque com sucesso', 'sucesso')
    except Exception as e:
        print(e)
        flash('Erro ao cadastrar item.', 'erro')

    return redirect(url_for('painel_admin', _anchor='estoque'))


#10.1.1 rota p editar um item do estoque (GET mostra o formulário, POST salva)
@app.route('/estoque/editar/<int:id_item>', methods=['GET', 'POST'])
def editar_estoque(id_item):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    if request.method == 'POST':
        nome_item = request.form['nome_item'].strip()
        unidade = request.form.get('unidade_medida', 'unidade').strip() or 'unidade'
        data_entrada = request.form.get('data_entrada') or None
        data_validade = request.form.get('data_validade') or None
        perecivel = 1 if request.form.get('perecivel') == 'sim' else 0

        #valida quantidade - mesma regra do cadastro: mínimo 1
        try:
            quantidade_num = int(request.form['quantidade_disponivel'])
        except (ValueError, TypeError):
            quantidade_num = 0

        if not nome_item or quantidade_num < 1:
            flash('Informe o nome do item e uma quantidade de no mínimo 1.', 'erro')
            return redirect(url_for('editar_estoque', id_item=id_item))

        #captura só o nome da nota fiscal nova, sem guardar o arquivo
        arquivo_nf = request.files.get('nota_fiscal')
        nota_fiscal = arquivo_nf.filename if arquivo_nf and arquivo_nf.filename else ''

        try:
            conexao = conectar_bd()
            cursor = conexao.cursor()

            if nota_fiscal:
                #arquivo novo escolhido: atualiza também o nome da nota fiscal
                cursor.execute("""
                    update estoque
                    set nome_item = %s, quantidade_disponivel = %s, unidade_medida = %s,
                        data_entrada = %s, data_validade = %s, perecivel = %s, nota_fiscal = %s
                    where id_item = %s
                """, (nome_item, quantidade_num, unidade, data_entrada, data_validade,
                      perecivel, nota_fiscal, id_item))
            else:
                #nenhum arquivo novo: mantém a nota fiscal que ja estava salva
                cursor.execute("""
                    update estoque
                    set nome_item = %s, quantidade_disponivel = %s, unidade_medida = %s,
                        data_entrada = %s, data_validade = %s, perecivel = %s
                    where id_item = %s
                """, (nome_item, quantidade_num, unidade, data_entrada, data_validade,
                      perecivel, id_item))

            conexao.commit()
            cursor.close()
            conexao.close()
            flash('Item atualizado com sucesso.', 'sucesso')
            return redirect(url_for('painel_admin', _anchor='estoque'))
        except Exception as e:
            print(e)
            flash('Erro ao atualizar item.', 'erro')
            return redirect(url_for('editar_estoque', id_item=id_item))

    #GET: busca o item pra preencher o formulário
    item = None
    try:
        conexao = conectar_bd()
        cursor = conexao.cursor(dictionary=True)
        cursor.execute("select * from estoque where id_item = %s", (id_item,))
        item = cursor.fetchone()
        cursor.close()
        conexao.close()
    except Exception as e:
        print(e)

    if not item:
        flash('Item não encontrado.', 'erro')
        return redirect(url_for('painel_admin', _anchor='estoque'))

    return render_template('editar_estoque.html', item=item)


#10.2 rota p excluir um item do estoque
@app.route('/estoque/excluir/<int:id_item>', methods=['POST'])
def excluir_estoque(id_item):
    if session.get('perfil') != 'admin':
        return redirect(url_for('login_admin'))

    try:
        conexao = conectar_bd()
        cursor = conexao.cursor()
        cursor.execute("delete from estoque where id_item = %s", (id_item,))
        conexao.commit()
        cursor.close()
        conexao.close()
        flash('Item removido do estoque.', 'sucesso')
    except Exception as e:
        print(e)
        flash('Erro ao excluir item.', 'erro')

    return redirect(url_for('painel_admin', _anchor='estoque'))


#11. rota p sair
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)