import json

from datos.viz.build_inversion import (
    OUT,
    anios_con_decreto,
    capacidad_operando,
    proyectos_aprobados,
)


def test_anios_con_decreto_cuenta_anios_distintos_de_un_rango():
    # 2008-11 a 2009-05 cubre 2008 y 2009
    assert anios_con_decreto([("2008", "2008-11-01", "2009-05-01")]) == 2


def test_decretos_solapados_no_cuentan_dos_veces_el_mismo_anio():
    d = [("2010", "2010-01-01", "2010-12-31"), ("2010", "2010-06-01", "2011-01-10")]
    assert anios_con_decreto(d) == 2


def test_sin_caducidad_cuenta_solo_el_anio_del_decreto():
    assert anios_con_decreto([("2019", "2019-07-19", "")]) == 1


def test_sin_fecha_decreto_usa_la_columna_anio():
    assert anios_con_decreto([("2011", "", "2011-08-17")]) == 1


def test_se_recorta_al_periodo_2008_2023():
    assert anios_con_decreto([("2022", "2022-05-01", "2025-05-01")]) == 2
    assert anios_con_decreto([("2005", "2005-05-01", "2009-01-01")]) == 2


def test_sin_decretos_es_cero():
    assert anios_con_decreto([]) == 0


def _sub(mva, estado="EN_OPERACION"):
    return {"capacidad_mva": mva, "estado": estado}


def test_red_electrica_suma_solo_en_operacion():
    filas = [_sub("100.0"), _sub("50.5"), _sub("999", "FUERA_DE_SERVICIO")]
    assert capacidad_operando(filas) == 150.5


def test_red_electrica_sin_subestaciones_es_cero_real():
    assert capacidad_operando([]) == 0.0


def test_red_electrica_sin_capacidad_en_ninguna_es_null():
    assert capacidad_operando([_sub(""), _sub("")]) is None


def test_red_electrica_ignora_las_que_no_traen_capacidad_si_otras_si():
    assert capacidad_operando([_sub(""), _sub("40")]) == 40.0


def _proy(codigos, estado="Aprobado", fecha="2020-03-01"):
    return {"codigos_comuna": codigos, "estado": estado, "fecha_presentacion": fecha}


def test_proyecto_multicomuna_cuenta_una_vez_en_cada_comuna():
    filas = [_proy("13101;13102"), _proy("13101")]
    assert proyectos_aprobados(filas) == {"13101": 2, "13102": 1}


def test_proyectos_filtra_estado_y_fecha():
    filas = [
        _proy("13101", estado="Rechazado"),
        _proy("13101", fecha="2014-12-31"),
        _proy("13101", fecha="2015-01-01"),
    ]
    assert proyectos_aprobados(filas) == {"13101": 1}


def test_codigo_repetido_en_un_proyecto_cuenta_una_vez():
    assert proyectos_aprobados([_proy("13101;13101")]) == {"13101": 1}


def test_json_generado_cumple_el_contrato():
    data = json.loads(OUT.read_text(encoding="utf-8"))
    codigos = [c["codigo"] for c in data["comunas"]]
    assert len(codigos) == 52 and codigos == sorted(codigos)
    ids = [i["id"] for i in data["indicadores"]]
    assert ids == ["escasez_hidrica", "sequia_futura", "red_electrica", "inversion_evaluada"]
    assert all(set(c["valores"]) == set(ids) for c in data["comunas"])
