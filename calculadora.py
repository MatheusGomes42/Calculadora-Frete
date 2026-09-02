import streamlit as st
import plotly.graph_objects as go
import math
import itertools
import random

# --- LÓGICA MATEMÁTICA E REGRAS DE NEGÓCIO ---

def atende_limite(x, y, z, peso, modalidade, limite_custom_air, limite_custom_ems, limite_custom_epacket):
    if modalidade == 'ePacket': 
        volumetria = x + y + z
        limite_efetivo = min(limite_custom_epacket, 900)
        return x <= 600 and volumetria <= limite_efetivo and peso <= 2000
        
    elif modalidade == 'Air Parcel': 
        volumetria = x + 2 * (y + z)
        limite_efetivo = min(limite_custom_air, 2000)
        return x <= 1050 and volumetria <= limite_efetivo and peso <= 30000
        
    elif modalidade == 'EMS': 
        volumetria = x + 2 * (y + z)
        limite_efetivo = min(limite_custom_ems, 3000)
        return x <= 1500 and volumetria <= limite_efetivo and peso <= 30000
        
    return False

def estimar_frete_jpy(modalidade, peso_g):
    if peso_g == 0: return 0
    if modalidade == 'ePacket':
        if peso_g > 2000: return None
        if peso_g <= 100: return 920
        return 920 + (math.ceil((peso_g - 100) / 100) * 260)
    elif modalidade == 'Air Parcel':
        if peso_g > 30000: return None
        if peso_g <= 1000: return 4550
        elif peso_g <= 10000: return 4550 + (math.ceil((peso_g - 1000) / 1000) * 2700)
        else: return 28850 + (math.ceil((peso_g - 10000) / 1000) * 1800)
    elif modalidade == 'EMS':
        if peso_g > 30000: return None
        if peso_g <= 500: return 3600
        elif peso_g <= 2000: return 3600 + (math.ceil((peso_g - 500) / 100) * 300)
        elif peso_g <= 6000: return 8100 + (math.ceil((peso_g - 2000) / 500) * 1500)
        else: return 20100 + (math.ceil((peso_g - 6000) / 1000) * 2400)
    return None

def calcular_taxa_servico(peso_g, modalidade, servico):
    if servico == "Nenhum": return 0
    
    if servico == "Caixa do Tesouro":
        if peso_g <= 500:
            if modalidade == 'ePacket': return 800
            return 400
        elif peso_g <= 1000:
            if modalidade == 'ePacket': return 1100
            return 800
        elif peso_g <= 1500:
            if modalidade == 'ePacket': return 1400
            elif modalidade == 'EMS': return 1600
            else: return 1200
        elif peso_g <= 2000:
            if modalidade == 'ePacket': return 1800
            elif modalidade == 'EMS': return 1800
            else: return 2000
        elif peso_g <= 4000: return 4000
        elif peso_g <= 5000: return 4000 if modalidade == 'EMS' else 6000
        elif peso_g <= 6000: return 6000
        elif peso_g <= 8000: return 6000 if modalidade == 'EMS' else 7000
        elif peso_g <= 10000: return 6000 if modalidade == 'EMS' else 8000
        elif peso_g <= 15000: return 8000
        elif peso_g <= 20000: return 10000
        elif peso_g <= 30000: return 15000 if modalidade == 'EMS' else 10000
        
    elif servico == "Gato Preto":
        if modalidade == 'ePacket':
            if peso_g <= 2000: return 1600
        elif modalidade == 'Air Parcel':
            if peso_g <= 2000: return 2000
            elif peso_g <= 3000: return 3000
            elif peso_g <= 4000: return 4000
            elif peso_g <= 6000: return 5000
            elif peso_g <= 8000: return 6000
            elif peso_g <= 15000: return 7000
            elif peso_g <= 30000: return 9000
    
    return 0

# --- MOTOR DE EMPACOTAMENTO 3D ---

def check_overlap(pos, dim, placed_items):
    x1, y1, z1 = pos
    dx1, dy1, dz1 = dim
    for p in placed_items:
        x2, y2, z2 = p['pos']
        dx2, dy2, dz2 = p['dim']
        if not (x1 + dx1 <= x2 or x2 + dx2 <= x1 or
                y1 + dy1 <= y2 or y2 + dy2 <= y1 or
                z1 + dz1 <= z2 or z2 + dz2 <= z1):
            return True
    return False

def get_candidate_points(placed_items):
    if not placed_items: return [(0, 0, 0)]
    xs = [0] + [p['pos'][0] + p['dim'][0] for p in placed_items]
    ys = [0] + [p['pos'][1] + p['dim'][1] for p in placed_items]
    zs = [0] + [p['pos'][2] + p['dim'][2] for p in placed_items]
    pts = list(set(itertools.product(xs, ys, zs)))
    pts.sort(key=lambda pt: (pt[2], pt[1], pt[0]))
    return pts

def run_packing(itens_ordenados, modalidade, limite_air, limite_ems, limite_epacket, tipo_prot, esp_prot, esp_cx, peso_cx):
    caixas = [] 
    rejeitados = []
    
    extra_dim = (2 * esp_cx)
    if tipo_prot == 'Conjunta':
        extra_dim += (2 * esp_prot)
        
    for item in itens_ordenados:
        dim_originais = (item['x'], item['y'], item['z'])
        rotacoes = list(set(itertools.permutations(dim_originais)))
        alocado = False
        
        for caixa in caixas:
            candidates = get_candidate_points(caixa['placed_items'])
            melhor_pos = None
            melhor_dim = None
            menor_vol_incremento = float('inf')
            
            for pt in candidates:
                for dim_rot in rotacoes:
                    if not check_overlap(pt, dim_rot, caixa['placed_items']):
                        new_max_x = max([p['pos'][0] + p['dim'][0] for p in caixa['placed_items']] + [pt[0] + dim_rot[0]])
                        new_max_y = max([p['pos'][1] + p['dim'][1] for p in caixa['placed_items']] + [pt[1] + dim_rot[1]])
                        new_max_z = max([p['pos'][2] + p['dim'][2] for p in caixa['placed_items']] + [pt[2] + dim_rot[2]])
                        
                        bounds = sorted([new_max_x + extra_dim, new_max_y + extra_dim, new_max_z + extra_dim], reverse=True)
                        new_peso_total = caixa['peso_itens'] + item['peso'] + peso_cx
                        
                        if atende_limite(bounds[0], bounds[1], bounds[2], new_peso_total, modalidade, limite_air, limite_ems, limite_epacket):
                            vol_temp = bounds[0] + 2*(bounds[1]+bounds[2]) if modalidade != 'ePacket' else bounds[0]+bounds[1]+bounds[2]
                            if vol_temp < menor_vol_incremento:
                                menor_vol_incremento = vol_temp
                                melhor_pos = pt
                                melhor_dim = dim_rot
                                caixa['temp_bounds'] = bounds
                                caixa['temp_maxes'] = (new_max_x, new_max_y, new_max_z)
                                
            if melhor_pos is not None:
                caixa['placed_items'].append({'item': item, 'pos': melhor_pos, 'dim': melhor_dim})
                caixa['x'], caixa['y'], caixa['z'] = caixa['temp_bounds']
                caixa['bound_x'], caixa['bound_y'], caixa['bound_z'] = caixa['temp_maxes']
                caixa['peso_itens'] += item['peso']
                caixa['peso_total'] = caixa['peso_itens'] + peso_cx
                alocado = True
                break
                
        if not alocado:
            bounds = sorted([dim_originais[0] + extra_dim, dim_originais[1] + extra_dim, dim_originais[2] + extra_dim], reverse=True)
            new_peso_total = item['peso'] + peso_cx
            
            if atende_limite(bounds[0], bounds[1], bounds[2], new_peso_total, modalidade, limite_air, limite_ems, limite_epacket):
                caixas.append({
                    'placed_items': [{'item': item, 'pos': (0,0,0), 'dim': dim_originais}],
                    'bound_x': dim_originais[0], 'bound_y': dim_originais[1], 'bound_z': dim_originais[2],
                    'x': bounds[0], 'y': bounds[1], 'z': bounds[2],
                    'peso_itens': item['peso'],
                    'peso_total': new_peso_total
                })
            else:
                rejeitados.append(item)
                
    return {'caixas': caixas, 'rejeitados': rejeitados}

def empacotar_heuristics(itens, modalidade, limite_air, limite_ems, limite_epacket, tipo_prot, esp_prot, esp_cx, peso_cx, servico, taxa_fixa):
    heuristics = [
        sorted(itens, key=lambda i: i['x']*i['y']*i['z'], reverse=True),
        sorted(itens, key=lambda i: i['peso'], reverse=True),
        sorted(itens, key=lambda i: i['peso']/(i['x']*i['y']*i['z'] + 1), reverse=True),
    ]
    
    random.seed(42)
    for _ in range(5):
        shuffled = itens[:]
        random.shuffle(shuffled)
        heuristics.append(shuffled)
        
    best_cost = float('inf')
    best_result = None
    best_error = "Nenhum item atende aos requisitos desta modalidade."
    
    for heur_itens in heuristics:
        result = run_packing(heur_itens, modalidade, limite_air, limite_ems, limite_epacket, tipo_prot, esp_prot, esp_cx, peso_cx)
        
        cost = 0
        valid = True
        for cx in result['caixas']:
            cx_frete = estimar_frete_jpy(modalidade, cx['peso_total'])
            if cx_frete is None:
                valid = False
                break
            
            cx_taxa = calcular_taxa_servico(cx['peso_total'], modalidade, servico)
            cost += (cx_frete + cx_taxa + taxa_fixa)
            
        if valid and cost < best_cost:
            best_cost = cost
            best_result = result
            
    if best_result is None or (len(best_result['caixas']) == 0 and len(best_result['rejeitados']) > 0):
        return best_error
        
    return best_result

# --- LÓGICA VISUAL (GRÁFICOS 3D INTERATIVOS) ---

def gerar_grafico_3d_novo(caixa_data):
    fig = go.Figure()
    cores = ['#E74C3C', '#3498DB', '#2ECC71', '#F1C40F', '#9B59B6', '#95A5A6', '#FF8C00']
    
    text_coords_x, text_coords_y, text_coords_z, text_content = [], [], [], []

    for i, p in enumerate(caixa_data['placed_items']):
        cor = cores[i % len(cores)]
        nome = p['item']['nome']
        x_pos, y_pos, z_pos = p['pos']
        dx, dy, dz = p['dim']
        
        x_verts = [x_pos, x_pos, x_pos+dx, x_pos+dx, x_pos, x_pos, x_pos+dx, x_pos+dx]
        y_verts = [y_pos, y_pos+dy, y_pos+dy, y_pos, y_pos, y_pos+dy, y_pos+dy, y_pos]
        z_verts = [z_pos, z_pos, z_pos, z_pos, z_pos+dz, z_pos+dz, z_pos+dz, z_pos+dz]
        
        i_faces = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j_faces = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k_faces = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        
        fig.add_trace(go.Mesh3d(
            x=x_verts, y=y_verts, z=z_verts,
            i=i_faces, j=j_faces, k=k_faces,
            color=cor, opacity=1.0, flatshading=True,
            name=nome, showlegend=True, hoverinfo='name'
        ))

        offset = 3 
        x_m, y_m, z_m = x_pos + dx/2, y_pos + dy/2, z_pos + dz/2
        
        face_centers = [
            (x_m, y_m, z_pos + dz + offset), (x_m, y_m, z_pos - offset),
            (x_m, y_pos - offset, z_m), (x_m, y_pos + dy + offset, z_m),
            (x_pos + dx + offset, y_m, z_m), (x_pos - offset, y_m, z_m)
        ]

        for fx, fy, fz in face_centers:
            text_coords_x.append(fx)
            text_coords_y.append(fy)
            text_coords_z.append(fz)
            text_content.append(nome)

    fig.add_trace(go.Scatter3d(
        x=text_coords_x, y=text_coords_y, z=text_coords_z,
        mode='text', text=text_content, textposition="middle center",
        textfont=dict(family="Arial, sans-serif", size=12, color="black"),
        hoverinfo='none', showlegend=False
    ))

    x_c, y_c, z_c = caixa_data['bound_x'], caixa_data['bound_y'], caixa_data['bound_z']
    x_ext = [0, x_c, x_c, 0, 0, 0, x_c, x_c, 0, 0, x_c, x_c, x_c, x_c, 0, 0]
    y_ext = [0, 0, y_c, y_c, 0, 0, 0, y_c, y_c, 0, 0, 0, y_c, y_c, y_c, y_c]
    z_ext = [0, 0, 0, 0, 0, z_c, z_c, z_c, z_c, z_c, z_c, 0, 0, z_c, z_c, 0]
    
    fig.add_trace(go.Scatter3d(
        x=x_ext, y=y_ext, z=z_ext, mode='lines',
        line=dict(color='red', width=4, dash='dash'),
        name='Espaço Interno Ocupado', hoverinfo='none'
    ))

    fig.update_layout(
        paper_bgcolor='white', plot_bgcolor='white', font=dict(color='black'),
        scene=dict(
            xaxis=dict(title='X (mm)', backgroundcolor='white', gridcolor='lightgray', showbackground=True),
            yaxis=dict(title='Y (mm)', backgroundcolor='white', gridcolor='lightgray', showbackground=True),
            zaxis=dict(title='Z (mm)', backgroundcolor='white', gridcolor='lightgray', showbackground=True),
            aspectmode='data'
        ),
        margin=dict(l=0, r=0, b=0, t=30), showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig

# --- FUNÇÃO AUXILIAR DE EXIBIÇÃO ---

def exibir_resultado_modalidade(mod, resultado, tipo_servico, taxa_fixa):
    caixas_geradas = resultado['caixas']
    itens_rejeitados = resultado['rejeitados']
    custo_total_jpy = resultado['custo_total']
    
    if itens_rejeitados:
        nomes_rejeitados = ", ".join([i['nome'] for i in itens_rejeitados])
        st.warning(f"🚫 **Atenção:** Os seguintes itens excedem os limites do **{mod}**: **{nomes_rejeitados}**")
    
    st.success(f"Total de caixas necessárias: {len(caixas_geradas)}")
    
    for idx, caixa in enumerate(caixas_geradas):
        nomes_conteudo = [p['item']['nome'] for p in caixa['placed_items']]
        
        volumetria = caixa['x'] + 2*(caixa['y']+caixa['z']) if mod != 'ePacket' else caixa['x']+caixa['y']+caixa['z']
        
        frete_base = estimar_frete_jpy(mod, caixa['peso_total'])
        taxa_servico = calcular_taxa_servico(caixa['peso_total'], mod, tipo_servico)
        custo_caixa = frete_base + taxa_servico + taxa_fixa
        
        texto_frete = f"¥ {custo_caixa:,.0f} (Frete: ¥{frete_base} | Serv: ¥{taxa_servico} | Fixo: ¥{taxa_fixa})"
        
        with st.expander(f"📦 Caixa {idx+1} ({len(caixa['placed_items'])} itens) | Peso: {caixa['peso_total']}g | Total: {texto_frete}"):
            st.write(f"**Conteúdo:** {', '.join(nomes_conteudo)}")
            st.write(f"**Peso Líquido dos Itens:** {caixa['peso_itens']}g | **Peso da Caixa Vazia:** {peso_caixa}g")
            st.write(f"**Dimensões Finais Externas:** X={caixa['x']}mm, Y={caixa['y']}mm, Z={caixa['z']}mm")
            st.write(f"**Volumetria Regra Postal:** {volumetria}mm")
            
            figura_grafico = gerar_grafico_3d_novo(caixa)
            st.plotly_chart(figura_grafico, use_container_width=True, key=f"grafico_{mod}_{idx}_{random.randint(1,10000)}")

    st.info(f"**Custo Total Estimado ({mod} c/ taxas): ¥ {custo_total_jpy:,.0f}**")


# --- GERENCIAMENTO DE ESTADO (LISTA DINÂMICA DE ITENS) ---

if 'itens' not in st.session_state:
    st.session_state.itens = [
        {'id': 1, 'nome': 'Figure 1', 'm1': 300, 'm2': 200, 'm3': 150, 'peso': 1500}
    ]
    st.session_state.next_id = 2

def add_item_cb():
    n_id = st.session_state.next_id
    st.session_state.itens.append({'id': n_id, 'nome': f'Item {n_id}', 'm1': 300, 'm2': 200, 'm3': 150, 'peso': 1500})
    st.session_state.next_id += 1

def remove_item_cb(uid):
    st.session_state.itens = [i for i in st.session_state.itens if i['id'] != uid]
    if len(st.session_state.itens) == 0:
        add_item_cb() # Garante que sempre terá pelo menos 1 item

def duplicate_item_cb(uid):
    idx = next(i for i, item in enumerate(st.session_state.itens) if item['id'] == uid)
    original = st.session_state.itens[idx]
    n_id = st.session_state.next_id
    nova_copia = original.copy()
    nova_copia['id'] = n_id
    nova_copia['nome'] += " (Cópia)"
    st.session_state.itens.insert(idx + 1, nova_copia)
    st.session_state.next_id += 1


# --- INTERFACE VISUAL DO APLICATIVO ---

st.set_page_config(page_title="Calculadora de Frete v4.0", page_icon="📦", layout="wide")
st.title("📦 Calculadora Inteligente de Frete (Japão ➔ Brasil)")

# --- BARRA LATERAL ---
st.sidebar.header("🛠️ Configurações da Caixa")
peso_caixa = st.sidebar.slider("Peso da Caixa Vazia (g)", 0, 2000, 300, 50)
espessura_caixa = st.sidebar.slider("Espessura do Papelão (mm)", 0, 20, 5, 1)

overhead_epacket = espessura_caixa * 6   
overhead_parcel = espessura_caixa * 10   
max_ui_epacket = 900 - overhead_epacket
max_ui_air = 2000 - overhead_parcel
max_ui_ems = 3000 - overhead_parcel

st.sidebar.divider()
st.sidebar.header("🫧 Plástico Bolha e Proteção")
espessura_protecao = st.sidebar.slider("Espessura da Proteção (mm)", 0, 50, 10, 1)
tipo_protecao = st.sidebar.radio("Como aplicar a proteção?", ["Individual (por item)", "Conjunta (na caixa inteira)"])

st.sidebar.divider()
st.sidebar.header("📋 Taxas Adicionais (Por Caixa)")
tipo_servico = st.sidebar.selectbox("Taxa de Serviço (Tabela)", ["Nenhum", "Caixa do Tesouro", "Gato Preto"])
taxa_fixa = st.sidebar.number_input("Taxa Fixa Adicional (¥)", min_value=0, value=0, step=100)

st.sidebar.divider()
st.sidebar.header("📏 Limites Volumétricos Úteis")
limite_epacket_interno = st.sidebar.number_input("Limite Útil ePacket (mm)", min_value=500, max_value=max_ui_epacket, value=min(850, max_ui_epacket), step=10)
limite_air_interno = st.sidebar.number_input("Limite Útil Air Parcel (mm)", min_value=500, max_value=max_ui_air, value=min(1800, max_ui_air), step=50)
limite_ems_interno = st.sidebar.number_input("Limite Útil EMS (mm)", min_value=500, max_value=max_ui_ems, value=min(2800, max_ui_ems), step=50)

# --- ÁREA PRINCIPAL (LISTA DINÂMICA DE ITENS) ---
st.subheader("🛒 Itens para Envio")
st.write("*(Dica: Adicione, duplique ou remova produtos usando os botões à direita)*")

# Cabeçalhos das Colunas
hcols = st.columns([2.5, 1, 1, 1, 1, 0.5, 0.5])
hcols[0].write("**Nome do Produto**")
hcols[1].write("**Med. 1 (mm)**")
hcols[2].write("**Med. 2 (mm)**")
hcols[3].write("**Med. 3 (mm)**")
hcols[4].write("**Peso (g)**")

itens_para_envio = []

# Loop desenhando os campos baseados no st.session_state
for item in st.session_state.itens:
    uid = item['id']
    cols = st.columns([2.5, 1, 1, 1, 1, 0.5, 0.5])
    
    # Text Inputs e Number Inputs salvam de volta no dicionário do item
    item['nome'] = cols[0].text_input("Nome", value=item['nome'], key=f"n_{uid}", label_visibility="collapsed")
    item['m1'] = cols[1].number_input("M1", min_value=1, value=item['m1'], key=f"m1_{uid}", label_visibility="collapsed")
    item['m2'] = cols[2].number_input("M2", min_value=1, value=item['m2'], key=f"m2_{uid}", label_visibility="collapsed")
    item['m3'] = cols[3].number_input("M3", min_value=1, value=item['m3'], key=f"m3_{uid}", label_visibility="collapsed")
    item['peso'] = cols[4].number_input("Peso", min_value=1, value=item['peso'], key=f"p_{uid}", label_visibility="collapsed")
    
    # Botões de Ação
    cols[5].button("📋", key=f"dup_{uid}", help="Duplicar este item", on_click=duplicate_item_cb, args=(uid,))
    cols[6].button("❌", key=f"rem_{uid}", help="Remover este item", on_click=remove_item_cb, args=(uid,))
    
    # Calcula as dimensões finais para a simulação com base na proteção
    if tipo_protecao == "Individual (por item)":
        dimensoes = sorted([item['m1'] + (2*espessura_protecao), item['m2'] + (2*espessura_protecao), item['m3'] + (2*espessura_protecao)], reverse=True)
    else:
        dimensoes = sorted([item['m1'], item['m2'], item['m3']], reverse=True)
        
    itens_para_envio.append({
        'nome': item['nome'], 
        'x': dimensoes[0], 
        'y': dimensoes[1], 
        'z': dimensoes[2], 
        'peso': item['peso']
    })

# Botão para adicionar item novo no final da lista
st.button("➕ Adicionar Novo Produto", on_click=add_item_cb)

st.divider()

if st.button("🚀 Calcular Melhor Opção de Envio", type="primary", use_container_width=True):
    modalidades = ['ePacket', 'Air Parcel', 'EMS']
    tipo_prot_str = "Individual" if "Individual" in tipo_protecao else "Conjunta"
    
    limite_ext_epacket = limite_epacket_interno + overhead_epacket
    limite_ext_air = limite_air_interno + overhead_parcel
    limite_ext_ems = limite_ems_interno + overhead_parcel
    
    resultados_calculados = []
    
    for mod in modalidades:
        resultado = empacotar_heuristics(
            itens_para_envio, mod, 
            limite_ext_air, limite_ext_ems, limite_ext_epacket, 
            tipo_prot_str, espessura_protecao, espessura_caixa, peso_caixa,
            tipo_servico, taxa_fixa
        )
        
        if not isinstance(resultado, str) and len(resultado['caixas']) > 0:
            custo_total_jpy = 0
            for cx in resultado['caixas']:
                f_base = estimar_frete_jpy(mod, cx['peso_total'])
                t_serv = calcular_taxa_servico(cx['peso_total'], mod, tipo_servico)
                custo_total_jpy += (f_base + t_serv + taxa_fixa)
                
            resultado['custo_total'] = custo_total_jpy
            resultado['qtd_rejeitados'] = len(resultado['rejeitados'])
            resultado['mod'] = mod
            resultados_calculados.append(resultado)
            
    # Ordem: Menos Rejeitados -> Evita EMS -> Mais Barato
    resultados_calculados.sort(key=lambda x: (
        x['qtd_rejeitados'], 
        1 if x['mod'] == 'EMS' else 0, 
        x['custo_total']
    ))
    
    if not resultados_calculados:
        st.error("Nenhum dos itens selecionados pode ser enviado pelas modalidades disponíveis.")
    else:
        melhor_opcao = resultados_calculados[0]
        outras_opcoes = resultados_calculados[1:]
        
        tab_melhor, tab_outras = st.tabs(["🏆 Melhor Opção", "📦 Outras Opções"])
        
        with tab_melhor:
            if melhor_opcao['mod'] == 'EMS':
                st.warning("⚠️ **Aviso:** EMS foi selecionado como a melhor (ou única) opção capaz de levar esta quantidade/tamanho de itens, mas lembre-se que a fiscalização tende a ser mais rigorosa.")
                
            st.header(f"✨ A Mais Vantajosa: {melhor_opcao['mod']}")
            exibir_resultado_modalidade(melhor_opcao['mod'], melhor_opcao, tipo_servico, taxa_fixa)
            
        with tab_outras:
            if outras_opcoes:
                for op in outras_opcoes:
                    st.subheader(f"✈️ Alternativa: {op['mod']}")
                    exibir_resultado_modalidade(op['mod'], op, tipo_servico, taxa_fixa)
                    st.write("---")
            else:
                st.write("Não há outras opções viáveis para este conjunto de itens (limite de tamanho/peso excedido nas outras modalidades).")
