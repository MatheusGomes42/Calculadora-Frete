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

def run_packing(itens_ordenados, modalidade, limite_air, limite_ems, limite_epacket, esp_cx, peso_cx):
    caixas = [] 
    rejeitados = []
    extra_dim = (2 * esp_cx)
        
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
            
            if modalidade == 'IGNORE_LIMITS' or atende_limite(bounds[0], bounds[1], bounds[2], new_peso_total, modalidade, limite_air, limite_ems, limite_epacket):
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

def empacotar_heuristics(itens, modalidade, limite_air, limite_ems, limite_epacket, esp_cx, peso_cx):
    heuristics = [
        sorted(itens, key=lambda i: i['x']*i['y']*i['z'], reverse=True),
        sorted(itens, key=lambda i: i['peso'], reverse=True),
    ]
    
    random.seed(42)
    for _ in range(3):
        shuffled = itens[:]
        random.shuffle(shuffled)
        heuristics.append(shuffled)
        
    best_cost = float('inf')
    best_result = None
    best_error = "Nenhum item atende aos requisitos desta modalidade."
    
    for heur_itens in heuristics:
        result = run_packing(heur_itens, modalidade, limite_air, limite_ems, limite_epacket, esp_cx, peso_cx)
        
        cost = 0
        valid = True
        for cx in result['caixas']:
            cx_cost = estimar_frete_jpy(modalidade, cx['peso_total'])
            if cx_cost is None:
                valid = False
                break
            cost += cx_cost
            
        if valid and cost < best_cost:
            best_cost = cost
            best_result = result
            
    if best_result is None or (len(best_result['caixas']) == 0 and len(best_result['rejeitados']) > 0):
        return best_error
        
    return best_result

# --- LÓGICA VISUAL MELHORADA (GRÁFICOS 3D INTERATIVOS) ---

def gerar_grafico_3d_novo(caixa_data):
    fig = go.Figure()
    cores = ['#E74C3C', '#3498DB', '#2ECC71', '#F1C40F', '#9B59B6', '#95A5A6', '#FF8C00']
    
    # Precisamos criar um índice de cor mutável para não repetir cores nos itens
    estado_cor = {'idx': 0}
    text_coords_x, text_coords_y, text_coords_z, text_content = [], [], [], []

    def draw_box(x_pos, y_pos, z_pos, dx, dy, dz, nome, cor, opacity=1.0, is_bubble=False):
        x_verts = [x_pos, x_pos, x_pos+dx, x_pos+dx, x_pos, x_pos, x_pos+dx, x_pos+dx]
        y_verts = [y_pos, y_pos+dy, y_pos+dy, y_pos, y_pos, y_pos+dy, y_pos+dy, y_pos]
        z_verts = [z_pos, z_pos, z_pos, z_pos, z_pos+dz, z_pos+dz, z_pos+dz, z_pos+dz]
        
        i_faces = [7, 0, 0, 0, 4, 4, 6, 6, 4, 0, 3, 2]
        j_faces = [3, 4, 1, 2, 5, 6, 5, 2, 0, 1, 6, 3]
        k_faces = [0, 7, 2, 3, 6, 7, 1, 1, 5, 5, 7, 6]
        
        fig.add_trace(go.Mesh3d(
            x=x_verts, y=y_verts, z=z_verts,
            i=i_faces, j=j_faces, k=k_faces,
            color=cor, opacity=opacity, flatshading=True,
            name=nome, showlegend=not is_bubble, hoverinfo='name'
        ))

        if not is_bubble:
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

    # Função matemática para descobrir como o motor 3D rotacionou o bloco inteiro
    def get_rotation_mapping(orig, rot):
        used = [False, False, False]
        mapping = [0, 0, 0]
        for i in range(3):
            for j in range(3):
                if rot[i] == orig[j] and not used[j]:
                    mapping[i] = j
                    used[j] = True
                    break
        return mapping

    for p in caixa_data['placed_items']:
        item = p['item']
        x_pos, y_pos, z_pos = p['pos']
        dx, dy, dz = p['dim']

        # SE FOR UM PACOTE AGRUPADO, NÓS DESMONTAMOS ELE VISUALMENTE!
        if item.get('is_grupo'):
            # Desenha a caixa translúcida (Plástico bolha compartilhado)
            draw_box(x_pos, y_pos, z_pos, dx, dy, dz, "Bolha (Grupo Compartilhado)", "lightblue", opacity=0.2, is_bubble=True)
            
            orig_dim = (item['x'], item['y'], item['z'])
            rot_dim = (dx, dy, dz)
            mapping = get_rotation_mapping(orig_dim, rot_dim)
            offset_bolha = item.get('bolha_offset', 0)
            
            # Desenha cada item dentro da bolha compartilhada
            for sp in item['sub_items']:
                sp_pos = sp['pos']
                sp_dim = sp['dim']
                
                # Aplica o offset do bolha para que elas fiquem no centro
                padded_pos = [sp_pos[0] + offset_bolha, sp_pos[1] + offset_bolha, sp_pos[2] + offset_bolha]
                
                # Mapeia as coordenadas caso o bloco inteiro tenha sido girado no Tetris principal
                rot_sp_pos = [padded_pos[mapping[0]], padded_pos[mapping[1]], padded_pos[mapping[2]]]
                rot_sp_dim = [sp_dim[mapping[0]], sp_dim[mapping[1]], sp_dim[mapping[2]]]
                
                # Posiciona absolutamente dentro da caixa
                abs_pos = [x_pos + rot_sp_pos[0], y_pos + rot_sp_pos[1], z_pos + rot_sp_pos[2]]
                
                cor = cores[estado_cor['idx'] % len(cores)]
                estado_cor['idx'] += 1
                draw_box(abs_pos[0], abs_pos[1], abs_pos[2], rot_sp_dim[0], rot_sp_dim[1], rot_sp_dim[2], sp['item']['nome'], cor)
                
        else:
            cor = cores[estado_cor['idx'] % len(cores)]
            estado_cor['idx'] += 1
            draw_box(x_pos, y_pos, z_pos, dx, dy, dz, item['nome'], cor)

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

# --- INTERFACE VISUAL DO APLICATIVO ---

st.set_page_config(page_title="Calculadora de Frete v4.6", page_icon="📦", layout="wide")
st.title("📦 Calculadora Inteligente de Frete (Japão ➔ Brasil)")

# --- BARRA LATERAL ---
st.sidebar.header("🛠️ Configurações da Caixa Externa")

peso_caixa = st.sidebar.slider("Peso da Caixa Vazia (g)", 0, 2000, 300, 50)
espessura_caixa = st.sidebar.slider("Espessura do Papelão (mm)", 0, 20, 5, 1)

overhead_epacket = espessura_caixa * 6
overhead_parcel = espessura_caixa * 10
max_ui_epacket = 900 - overhead_epacket
max_ui_air = 2000 - overhead_parcel
max_ui_ems = 3000 - overhead_parcel

st.sidebar.divider()
st.sidebar.header("🫧 Espessura da Proteção")
espessura_protecao = st.sidebar.slider("Plástico Bolha (mm)", 0, 50, 10, 1)

st.sidebar.divider()
st.sidebar.header("📏 Limites Volumétricos Úteis")

limite_epacket_interno = st.sidebar.number_input("Limite Útil ePacket (mm)", min_value=500, max_value=max_ui_epacket, value=min(850, max_ui_epacket), step=10)
limite_air_interno = st.sidebar.number_input("Limite Útil Air Parcel (mm)", min_value=500, max_value=max_ui_air, value=min(1800, max_ui_air), step=50)
limite_ems_interno = st.sidebar.number_input("Limite Útil EMS (mm)", min_value=500, max_value=max_ui_ems, value=min(2800, max_ui_ems), step=50)

st.write("---")
st.subheader("📝 Itens para Envio")
st.write("Selecione **'Compartilhar Bolha'** para agrupar figuras e passar o bolha como se fossem um bloco só, economizando muito espaço.")

num_figures = st.number_input("Quantos itens vai enviar?", min_value=1, max_value=15, value=1)
itens_individuais = []
itens_para_agrupar = []

for i in range(num_figures):
    col0, col1, col2, col3, col4, col5 = st.columns([1.5, 0.8, 0.8, 0.8, 0.8, 1.5]) 
    
    with col0: nome_item = st.text_input(f"Item {i+1}", value=f"Figure {i+1}", key=f"nome_{i}")
    with col1: m1 = st.number_input("M1 (mm)", min_value=1, value=300, key=f"m1_{i}")
    with col2: m2 = st.number_input("M2 (mm)", min_value=1, value=200, key=f"m2_{i}")
    with col3: m3 = st.number_input("M3 (mm)", min_value=1, value=150, key=f"m3_{i}")
    with col4: peso = st.number_input("Peso (g)", min_value=1, value=1500, key=f"peso_{i}")
    with col5: 
        st.write("Como proteger?")
        tipo_prot = st.radio("Proteção", ["Individual", "Compartilhar Bolha"], horizontal=True, label_visibility="collapsed", key=f"prot_{i}")
        
    if tipo_prot == "Individual":
        dimensoes = sorted([m1 + (2*espessura_protecao), m2 + (2*espessura_protecao), m3 + (2*espessura_protecao)], reverse=True)
        itens_individuais.append({'nome': nome_item, 'x': dimensoes[0], 'y': dimensoes[1], 'z': dimensoes[2], 'peso': peso})
    else:
        dimensoes = sorted([m1, m2, m3], reverse=True)
        itens_para_agrupar.append({'nome': nome_item, 'x': dimensoes[0], 'y': dimensoes[1], 'z': dimensoes[2], 'peso': peso})

st.divider()

if st.button("Calcular Empacotamento Inteligente", type="primary", use_container_width=True):
    lista_final_de_itens = itens_individuais.copy()
    
    if len(itens_para_agrupar) > 0:
        resultado_agrupamento = run_packing(
            sorted(itens_para_agrupar, key=lambda i: i['x']*i['y']*i['z'], reverse=True),
            'IGNORE_LIMITS', 99999, 99999, 99999, 0, 0
        )
        
        bloco_agrupado = resultado_agrupamento['caixas'][0] 
        nomes_agrupados = " + ".join([i['nome'] for i in itens_para_agrupar])
        
        macro_x = bloco_agrupado['bound_x'] + (2 * espessura_protecao)
        macro_y = bloco_agrupado['bound_y'] + (2 * espessura_protecao)
        macro_z = bloco_agrupado['bound_z'] + (2 * espessura_protecao)
        
        lista_final_de_itens.append({
            'nome': f"Grupo Bolha Compartilhado",
            'x': macro_x,
            'y': macro_y,
            'z': macro_z,
            'peso': bloco_agrupado['peso_itens'],
            'is_grupo': True, # Variável mágica para o gráfico não apagar elas!
            'sub_items': bloco_agrupado['placed_items'],
            'bolha_offset': espessura_protecao
        })

    modalidades = ['ePacket', 'Air Parcel', 'EMS']
    limite_ext_epacket = limite_epacket_interno + overhead_epacket
    limite_ext_air = limite_air_interno + overhead_parcel
    limite_ext_ems = limite_ems_interno + overhead_parcel
    
    for mod in modalidades:
        st.subheader(f"✈️ Frete: {mod}")
        
        resultado = empacotar_heuristics(
            lista_final_de_itens, mod, 
            limite_ext_air, limite_ext_ems, limite_ext_epacket, 
            espessura_caixa, peso_caixa
        )
        
        if isinstance(resultado, str):
            st.error(resultado)
        else:
            caixas_geradas = resultado['caixas']
            itens_rejeitados = resultado['rejeitados']
            custo_total_jpy = 0
            
            if itens_rejeitados:
                nomes_rejeitados = ", ".join([i['nome'] for i in itens_rejeitados])
                st.warning(f"🚫 **Atenção:** Os seguintes itens excedem os limites do **{mod}**: **{nomes_rejeitados}**")
            
            if caixas_geradas:
                st.success(f"Total de caixas necessárias: {len(caixas_geradas)}")
                
                for idx, caixa in enumerate(caixas_geradas):
                    nomes_conteudo = []
                    for p in caixa['placed_items']:
                        if p['item'].get('is_grupo'):
                            nomes_conteudo.extend([sub['item']['nome'] for sub in p['item']['sub_items']])
                        else:
                            nomes_conteudo.append(p['item']['nome'])
                            
                    volumetria = caixa['x'] + 2*(caixa['y']+caixa['z']) if mod != 'ePacket' else caixa['x']+caixa['y']+caixa['z']
                    valor_frete = estimar_frete_jpy(mod, caixa['peso_total'])
                    
                    if valor_frete:
                        custo_total_jpy += valor_frete
                        texto_frete = f"¥ {valor_frete:,.0f}"
                    else:
                        texto_frete = "Erro no cálculo"
                    
                    with st.expander(f"📦 Caixa {idx+1} ({len(nomes_conteudo)} itens) | Peso Total: {caixa['peso_total']}g | Frete: {texto_frete}"):
                        st.write(f"**Conteúdo:** {', '.join(nomes_conteudo)}")
                        st.write(f"**Peso Líquido:** {caixa['peso_itens']}g | **Peso da Caixa Vazia:** {peso_caixa}g")
                        st.write(f"**Dimensões Finais Externas:** X={caixa['x']}mm, Y={caixa['y']}mm, Z={caixa['z']}mm")
                        
                        figura_grafico = gerar_grafico_3d_novo(caixa)
                        st.plotly_chart(figura_grafico, use_container_width=True, key=f"grafico_{mod}_{idx}")
                
                if custo_total_jpy > 0:
                    st.info(f"**Custo Total Estimado ({mod}): ¥ {custo_total_jpy:,.0f}**")
            elif not caixas_geradas and itens_rejeitados:
                st.error(f"Nenhum item cabe no {mod}.")
                
        st.write("---")
