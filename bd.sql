create database cantina character set utf8mb4 collate utf8mb4_unicode_ci;
use cantina;


-- 1. Tabela Alunos
create table alunos (
id_aluno int auto_increment primary key,
nome varchar(80) not null,
matricula varchar(12) not null unique,
senha varchar(12) not null,
turma varchar(20) not null default 'Não informada',
status_cadastro varchar(20) not null default 'Ativo',
comorbidades varchar(80) default '',
atestado_arquivo varchar(125) default '',
data_cadastro timestamp default current_timestamp
)engine=innodb default charset=utf8mb4;

-- 1.2 Alunos com Comorbidades e Restrições preenchidas
insert into alunos (id_aluno, nome, matricula, senha, turma, status_cadastro, comorbidades, atestado_arquivo) values
(1, 'LUCAS CAMACHO', '123', '123', '3º ANO A', 'ativo', 'Diabetes, Intolerância a lactose', 'atestado_lucas_camacho.pdf'),
(2, 'MARIA SILVA', '456', '456', '2º ANO B', 'ativo', 'Intolerância a lactose', ''),
(3, 'JOÃO COSTA', '789', '789', '1º ANO C', 'ativo', '', ''),
(4, 'ANA BEATRIZ LIMA', '001', '001', '1º ANO A', 'ativo', '', ''),
(5, 'LUCAS PEREIRA', '002', '002', '2º ANO A', 'ativo', 'Alergia a amendoim', ''),
(6, 'FERNANDA OLIVEIRA', '003', '003', '3º ANO B', 'ativo', '', ''),
(7, 'RAFAEL SANTOS', '004', '004', '2º ANO C', 'ativo', '', ''),
(8, 'JULIANA MARTINS', '005', '005', '1º ANO B', 'ativo', 'Diabetes', ''),
(9, 'PEDRO ALVES', '006', '006', '3º ANO C', 'ativo', '', ''),
(10, 'CAMILA  RODRIGUES', '007', '007', '2º ANO B', 'ativo', '', ''),
(11, 'THIAGO NASCIMENTO', '008', '008', '1º ANO A', 'ativo', '', ''),
(12, 'LARISSA PEREIRA', '009', '009', '3º ANO A', 'ativo', '', '');


-- 2. Tabela  Admins
create table usuarios (
id_usuario int auto_increment primary key,
nome varchar(50) not null,
login varchar(20) not null unique,
senha varchar(20) not null,
perfil enum('admin', 'nutricionista') not null)
engine=innodb default charset=utf8mb4;

-- 2.1 Usuários Admins
insert into usuarios (id_usuario, nome, login, senha, perfil) values
(1, 'Administrador', 'admin', 'admin123', 'admin'),
(2, 'Ana nutricionista', 'nutri', 'nutri123', 'nutricionista');


-- 3. Tabela Cardápio semanal
create table cardapio (
id_cardapio int auto_increment primary key,
dia_semana varchar(30) not null,
refeicao_principal varchar(80) not null,
acompanhamentos varchar(60) default '',
fruta_sobremesa varchar(60) default '')
engine=innodb default charset=utf8mb4;

-- 3.1 Cardápio semanal
insert into cardapio (id_cardapio, dia_semana, refeicao_principal, acompanhamentos, fruta_sobremesa) values
(1, 'Segunda-feira', 'Frango Grelhado', 'Arroz, Feijão e Salada verde', '🍌 Banana'),
(2, 'Terça-feira', 'Macarrão ao Molho', 'Salada Verde', '🍊 Laranja'),
(3, 'Quarta-feira', 'Bife Acebolado', 'Arroz, Lentilha e Cenoura Cozida', '🍎 Maçã'),
(4, 'Quinta-feira', 'Peixe Assado', 'Arroz, Feijão e Brócolis', '🍈 Melão'),
(5, 'Sexta-feira', 'Frango à Parmegiana', 'Arroz, Feijão e Purê de Batata', '🍮 Gelatina');


-- 4. Tabela Agendamentos
create table agendamentos (
id_grid_reserva int auto_increment primary key,
id_aluno int not null,
id_cardapio int not null,
data_reserva timestamp default current_timestamp,
status_reserva varchar(20) not null default 'Confirmado',
foreign key (id_cardapio) references cardapio(id_cardapio),
foreign key (id_aluno) references alunos(id_aluno) on delete cascade)
engine=innodb default charset=utf8mb4;


-- 5. Tabela avisos
create table avisos (
id_aviso int auto_increment primary key,
titulo varchar(100) not null,
conteudo text not null,
tipo_icone varchar(20) default 'bell',
data_publicacao timestamp default current_timestamp,
ativo tinyint(1) default 1)
engine=innodb default charset=utf8mb4;

-- 5.1 Mural de avisos da pág inicial
insert into avisos (id_aviso, titulo, conteudo, tipo_icone) values
(1, 'DISTRIBUIÇÃO DE LANCHES', 'AMANHÃ A DISTRIBUIÇÃO COMEÇARA ÁS 10h NO REFEITÓRIO.', 'bell'),
(2, 'CARDÁPIO ESPECIAL', 'PREPARAMOS UM DIA DA SAÚDE NESTA SEMANA COM FRUTAS E SUCOS NATURAIS!', 'star'),
(3, 'LEMBRETE IMPORTANTE', 'ATUALIZE SEU CADASTRO NA SECRETARIA CASO MUDE DE TURMA.', 'info'),
(4, 'SEMANA DA NUTRIÇÃO', 'DE 15 A 19 DE JUNHO TEREMOS PALESTRAS SOBRE ALIMENTAÇÃO SAUDÁVEL.', 'leaf'),
(5, 'NOVO HORÁRIO', 'A PARTIR DE SEGUNDA-FEIRA O REFEITÓRIO ABRE ÁS 11h30 E FECHA ÁS 12H15.', 'clock');


-- 6. Tabela Estoque
create table estoque (
id_item int auto_increment primary key,
nome_item varchar(50) not null,
quantidade_disponivel int not null default 0,
unidade_medida varchar(10) not null default 'unidade',
data_entrada date default null,
data_validade date default null,
nota_fiscal varchar(50) default '',
perecivel tinyint(1) not null default 1)
engine=innodb default charset=utf8mb4;
commit;

