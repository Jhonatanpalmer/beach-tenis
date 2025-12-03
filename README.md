# Beach Tennis Manager

Aplicação Django construída para gerenciar cadastros, duplas e torneios de Beach Tennis com controle de categorias (A–D) e critério de desempate por pontos acumulados (15/30/40/GAME).

## Requisitos atendidos

- Cadastro de participantes com nome, data de nascimento, gênero (Masculino/Feminino/Mista) e categoria.
- Cadastro de categorias padrão (A, B, C, D) com possibilidade de criar novas pelo painel.
- Montagem de duplas (masculinas, femininas ou mistas) garantindo combinações válidas.
- Criação de torneios com configuração de tie-break (7 ou 10 pontos / vitória por +2).
- Registro de partidas por torneio, anotando quantidade de sets, games por set, tie-break e sequência de pontos (15/30/40/GAME) usada em critérios de desempate.
- Classificação automática por torneio (vitórias ➜ sets ➜ pontos acumulados).
- Torneio Rápido independente: basta informar os nomes, escolher entre montar ou sortear as duplas e registrar o placar de cada partida com destaque para vencedores/perdedores.

## Como executar

```bash
cd /d/BT
D:/BT/venv/Scripts/python.exe manage.py runserver
```

A aplicação estará disponível em `http://127.0.0.1:8000/` com telas para dashboard, categorias, participantes, duplas, torneios e o novo modo Torneio Rápido.

## Fluxo sugerido

1. Cadastre ou ajuste as categorias (já existem A, B, C e D).
2. Registre participantes informando categoria e gênero.
3. Monte as duplas conforme divisão desejada (Masculina, Feminina ou Mista).
4. Crie um torneio e, na página de detalhes, cadastre as partidas necessárias.
5. Após cada partida, use o botão “Registrar resultado” para lançar sets, tie-break e sequência de pontos. A classificação será recalculada automaticamente.
6. Para eventos rápidos, abra “Torneio Rápido”, informe o nome do evento e os participantes (um por linha). Depois forme ou sorteie as duplas e registre o placar: vencedores ficam em verde e perdedores em vermelho automaticamente.
