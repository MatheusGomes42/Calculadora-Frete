import streamlit as st
import plotly.graph_objects as go
import math
import itertools
import random

# --- LÓGICA MATEMÁTICA E REGRAS DE NEGÓCIO ---

def atende_limite(x, y, z, peso, modalidade, limite_custom_air, limite_custom_ems):
    # As variáveis x, y, z aqui já incluem a caixa e a proteção. Não precisamos somar folgas extras.
    if modalidade == 'ePacket': 
        volumetria = x + y + z
        return x <= 600 and volumetria <= 850 and peso <= 2000
        
    elif modalidade == 'Air Parcel': 
        volumetria = x + 2 * (y + z)
        limite_efetivo = min(limite_custom_air, 1950)
        return x <= 1050 and volumetria <= limite_efetivo and peso <= 30000
        
    elif modalidade == 'EMS': 
        volumetria = x + 2 * (y + z)
        limite_efetivo = min(limite_custom_ems, 2950)
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

def run_packing(itens_ordenados, modalidade, limite_air, limite_ems, tipo_prot, esp_prot, esp_cx, peso_cx):
    caixas = [] 
    
    # Se uma espessura tem X mm, ela soma 2*X na dimensão total (pois vai dos dois lados)
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
                        
                        if atende_limite(bounds[0], bounds[1], bounds[2], new_peso_total, modalidade, limite_air, limite_ems):
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
            
            if atende_limite(bounds[0], bounds[1], bounds[2], new_peso_total, modalidade, limite_air, limite_ems):
                caixas.append({
                    'placed_items': [{'item': item, 'pos': (0,0,0), 'dim': dim_originais}],
                    'bound_x': dim_originais[0], 'bound_y': dim_originais[1], 'bound_z': dim_originais[2],
                    'x': bounds[0], 'y': bounds[1], 'z': bounds[2],
                    'peso_itens': item['peso'],
                    'peso_total': new_peso_total
                })
            else:
                return f"❌ O item '{item['nome']}' excede os limites para {modalidade} mesmo sozinho!"
                
    return caixas

def empacotar_heuristics(itens, modalidade, limite_air, limite_ems, tipo_prot, esp_prot, esp_cx, peso_cx):
    # Diferentes estratégias para tentar fugir de uma quebra de peso ruim (ex: 3.1kg vs 2.1kg)
    heuristics = [
        sorted(itens, key=lambda i: i['x']*i['y']*i['z'], reverse=True), # Por Volume
        sorted(itens, key=lambda i: i['peso'], reverse=True),            # Por Peso
        sorted(itens, key=lambda i: i['peso']/(i['x']*i['y']*i['z'] + 1), reverse=True), # Por Densidade
    ]
    
    random.seed(42) # Reproduzibilidade
    for _ in range(5):
        shuffled = itens[:]
        random.shuffle(shuffled)
        heuristics.append(shuffled)
        
    best_cost = float('inf')
    best_result = None
    best_error = "Não foi possível empacotar os itens."
    
    for heur_itens in heuristics:
        result = run_packing(heur_itens, modalidade, limite_air, limite_ems, tipo_prot, esp_prot, esp_cx, peso_cx)
        
        if isinstance(result, str):
            best_error = result
            continue
            
        # Avalia o custo financeiro desta organização
        cost = 0
        valid = True
        for cx in result:
            cx_cost = estimar_frete_jpy(modalidade, cx['peso_total'])
            if cx_cost is None:
                valid = False
                break
            cost += cx_cost
            
        if valid and cost < best_cost:
            best_cost = cost
            best_result = result
            
    return best_result if best_result is not None else best_error

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

    # Desenha a caixa limite (bounding box dos itens internos)
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

# --- INTERFACE VISUAL DO APLICATIVO ---

st.set_page_config(page_title="Calculadora de Frete v3", page_icon="📦", layout="wide")
st.title("📦 Calculadora Inteligente de Frete (Japão ➔ Brasil)")

# --- BARRA LATERAL ---
st.sidebar.header("🛠️ Configurações da Caixa")

peso_caixa = st.sidebar.slider("Peso da Caixa Vazia (g)", 0, 2000, 300, 50, help="Será somado ao peso final dos itens.")
espessura_caixa = st.sidebar.slider("Espessura do Papelão (mm)", 0, 20, 5, 1, help="Espessura da parede da caixa. Ex: 5mm de cada lado = 1cm a mais na dimensão.")

st.sidebar.divider()
st.sidebar.header("🫧 Plástico Bolha e Proteção")
espessura_protecao = st.sidebar.slider("Espessura da Proteção (mm)", 0, 50, 10, 5, help="Camada de plástico bolha/jornal.")
tipo_protecao = st.sidebar.radio("Como aplicar a proteção?", 
    ["Individual (por item)", "Conjunta (na caixa inteira)"],
    help="Individual envolve cada figure (bom se tiverem caixas separadas). Conjunta envolve todas juntas se estiverem coladas."
)

st.sidebar.divider()
st.sidebar.header("📏 Limites Postais")
limite_air = st.sidebar.number_input("Limite Air Parcel (mm)", min_value=500, max_value=1950, value=1800, step=50)
limite_ems = st.sidebar.number_input("Limite EMS (mm)", min_value=500, max_value=2950, value=2800, step=50)


num_figures = st.number_input("Quantos itens vai enviar?", min_value=1, max_value=15, value=1)
itens_para_envio = []

st.write(f"*(Dica: Se a proteção for **Individual**, ela será somada automaticamente abaixo)*")

for i in range(num_figures):
    col0, col1, col2, col3, col4 = st.columns([2, 1, 1, 1, 1]) 
    with col0: nome_item = st.text_input(f"Item {i+1}", value=f"Figure {i+1}", key=f"nome_{i}")
    with col1: m1 = st.number_input("Med. 1 (mm)", min_value=1, value=300, key=f"m1_{i}")
    with col2: m2 = st.number_input("Med. 2 (mm)", min_value=1, value=200, key=f"m2_{i}")
    with col3: m3 = st.number_input("Med. 3 (mm)", min_value=1, value=150, key=f"m3_{i}")
    with col4: peso = st.number_input("Peso (g)", min_value=1, value=1500, key=f"peso_{i}")
        
    # Aplica a proteção individual se selecionado
    if tipo_protecao == "Individual (por item)":
        dimensoes = sorted([m1 + (2*espessura_protecao), m2 + (2*espessura_protecao), m3 + (2*espessura_protecao)], reverse=True)
    else:
        dimensoes = sorted([m1, m2, m3], reverse=True)
    
    itens_para_envio.append({
        'nome': nome_item, 
        'x': dimensoes[0], 
        'y': dimensoes[1], 
        'z': dimensoes[2], 
        'peso': peso
    })

st.divider()

if st.button("Calcular Empacotamento Inteligente", type="primary", use_container_width=True):
    modalidades = ['ePacket', 'Air Parcel', 'EMS']
    tipo_prot_str = "Individual" if "Individual" in tipo_protecao else "Conjunta"
    
    for mod in modalidades:
        st.subheader(f"✈️ Frete: {mod}")
        
        # O sistema agora tenta várias combinações para evitar faixas de peso desfavoráveis!
        resultado = empacotar_heuristics(itens_para_envio, mod, limite_air, limite_ems, tipo_prot_str, espessura_protecao, espessura_caixa, peso_caixa)
        
        if isinstance(resultado, str):
            st.error(resultado)
        else:
            custo_total_jpy = 0
            st.success(f"Total de caixas necessárias: {len(resultado)}")
            
            for idx, caixa in enumerate(resultado):
                nomes_conteudo = [p['item']['nome'] for p in caixa['placed_items']]
                
                volumetria = caixa['x'] + 2*(caixa['y']+caixa['z']) if mod != 'ePacket' else caixa['x']+caixa['y']+caixa['z']
                valor_frete = estimar_frete_jpy(mod, caixa['peso_total'])
                
                if valor_frete:
                    custo_total_jpy += valor_frete
                    texto_frete = f"¥ {valor_frete:,.0f}"
                else:
                    texto_frete = "Erro no cálculo (Peso estourou)"
                
                with st.expander(f"📦 Caixa {idx+1} ({len(caixa['placed_items'])} itens) | Peso Total: {caixa['peso_total']}g | Frete Exato: {texto_frete}"):
                    st.write(f"**Conteúdo:** {', '.join(nomes_conteudo)}")
                    st.write(f"**Peso Líquido dos Itens:** {caixa['peso_itens']}g | **Peso da Caixa Vazia:** {peso_caixa}g")
                    st.write(f"**Dimensões Finais Externas (Caixa Fechada):** X={caixa['x']}mm, Y={caixa['y']}mm, Z={caixa['z']}mm")
                    st.write(f"**Volumetria Regra Postal:** {volumetria}mm")
                    
                    figura_grafico = gerar_grafico_3d_novo(caixa)
                    st.plotly_chart(figura_grafico, use_container_width=True, key=f"grafico_{mod}_{idx}")
            
            if custo_total_jpy > 0:
                st.info(f"**Custo Total Estimado ({mod}): ¥ {custo_total_jpy:,.0f}**")
        st.write("---")
