from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector

app = Flask(__name__)
app.secret_key = 'chave_secreta_cantina'

#lista fixa de comorbidades que aparecem no forms do aluno
LISTA_COMORBIDADES = ['Diabetes', 'Intolerancia a Lactose', 'Alergia a Amendoim', 'Doenca Celiaca', 'Hipertensao']


#conexao com o bd
def conectar_bd():
    return mysql.connector.connect(
        host='localhost',
        user='root',
        password='',
        database='cantina')


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

        cursor.execute("select * from avisos where ativo = 1")
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
                "insert into alunos (nome, matricula, senha, turma) values (%s, %s, %s, %s)",
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

        cursor.execute("select * from avisos where ativo = 1")
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
        flash('Refeição agendada com sucesso!', 'Sucesso')
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
        cursor.execute("delete from agendamentos where id_grid_reserva = %s", (id_reserva,))
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
    total_agendamentos=total_agendamentos, total_itens_estoque=len(estoque), relatorio_agend=relatorio_agend)



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
        return redirect(url_for('painel_admin'))

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

    return redirect(url_for('painel_admin'))


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

    return redirect(url_for('painel_admin'))


#11. rota p sair
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

