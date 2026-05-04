"""
DDL Firebird (dominios, tablas, triggers) para bases Exógena.

La carga inicial de datos no va aquí: la orquesta ``infrastructure.adapters.fn_bd_helisa``.
"""
def Dominios(conexion):
    #Crea dominios en la base de datos
    if conexion:
        cursor = conexion.cursor()
        cursor.execute("create domain dmFecha as date")
        cursor.execute("create domain dmEntero004 as smallint")
        cursor.execute("create domain dmEntero008 as integer")
        cursor.execute("create domain dmCadena001 as varchar(1)")
        cursor.execute("create domain dmCadena002 as varchar(2)")
        cursor.execute("create domain dmCadena010 as varchar(10)")
        cursor.execute("create domain dmCadena020 as varchar(20)")
        cursor.execute("create domain dmCadena030 as varchar(30)")
        cursor.execute("create domain dmCadena060 as varchar(60)")
        cursor.execute("create domain dmCadena100 as varchar(100)")
        cursor.execute("create domain dmCadena128 as varchar(128)")
        cursor.execute("create domain dmCadena200 as varchar(200)")
        cursor.execute("create domain dmCadena256 as varchar(256)")
        cursor.execute("create domain dmCadena450 as varchar(450)")
        cursor.execute("create domain dmCadena512 as varchar(512)")
        cursor.execute("create domain dmMoneda as numeric(15, 2)")
        cursor.execute("CREATE DOMAIN dmBlobText AS BLOB SUB_TYPE 1 SEGMENT SIZE 80 CHARACTER SET ISO8859_1;")
        cursor.close()

def Usuarios(conexion):
    """
    Crea la tabla Usuarios
    """
    tabla = "Usuarios"
    if conexion:
        cursor = conexion.cursor()
        cursor.execute(f"""
                       create table {tabla}
                       (Id                      dmEntero004 not null,
                        Nombre                  dmCadena030,
                        email                   dmCadena060,
                        clave                   dmCadena030,
                        activo                  dmCadena001
                       )
                       """)
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")
        conexion.commit()
        cursor.execute(f"insert into {tabla} (id, nombre, email, clave, activo) values (1, 'A', '', '1', 'S')")
        # Crear generador
        cursor.execute("create sequence GEN_USUARIOS_ID")
        cursor.execute(f"set generator GEN_USUARIOS_ID to 1")
        # Crear trigger 
        cursor.execute("""
            create trigger BI_USUARIOS_ID for Usuarios
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_USUARIOS_ID;
            end
        """)
        conexion.commit()
        
        

def Empresas(conexion):
    if conexion:
        tabla = "Empresas"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}
            (Id                      dmEntero004 not null,
             Identidad               dmCadena020,
             Nombre                  dmCadena256,
             CodigoEmpresaNI         dmEntero004,
             CodigoEmpresaPH         dmEntero004,
             ConsorciosActivo        dmCadena001,
             Direccion               dmCadena256,
             Municipio               dmEntero004,
             Departamento            dmEntero004,
             Pais                    dmEntero004
            )
        """)
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")

        # Crear generador
        cursor.execute("create sequence GEN_EMPRESAS_ID")

        # Crear trigger 
        cursor.execute("""
            create trigger BI_EMPRESAS_ID for Empresas
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_EMPRESAS_ID;
            end
        """)

        conexion.commit()

def Consorcios(conexion):
    if conexion:
        tabla = "Consorcios"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}
            (Id                      dmEntero004 not null,
             Identidad               dmEntero008,
             IdentidadEmpresa        dmEntero004,
             Nombre                  dmCadena256,
             TipoDocumento           dmCadena030,
             NoFideicomiso           dmEntero008,
             Porcentaje              dmEntero004,
             TipoContrato            dmCadena100
            )
        """)
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")

        cursor.execute("create sequence GEN_CONSORCIOS_ID")

        cursor.execute(f"""
            create trigger BI_CONSORCIOS_ID for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_CONSORCIOS_ID;
            end
        """)

        conexion.commit()
        
def Terceros(conexion, codigo, producto):
    if conexion:
        tabla = "Terceros"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}(
                Id                  dmEntero004 not null,
                TipoDocumento       dmEntero004,
                Identidad           dmCadena020,
                Naturaleza          dmEntero004,
                DigitoVerificacion  dmCadena002,
                RazonSocial         dmCadena450,
                PrimerApellido      dmCadena060,
                SegundoApellido     dmCadena060,
                PrimerNombre        dmCadena060,
                SegundoNombre       dmCadena060,
                Direccion           dmCadena200,
                Departamento        dmEntero004,
                Municipio           dmEntero004,
                Pais                dmEntero004
                )"""
            )
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")
        
        cursor.execute(f"create sequence GEN_{tabla}_ID")

        cursor.execute(f"""
            create trigger BI_{tabla}_ID for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_{tabla}_ID;
            end
        """)

        conexion.commit()

def Cuentas_trib(conexion, codigo, producto):
    if conexion:
        tabla = "Cuentas_trib"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}(
                Id                  dmEntero004 not null,
                Codigo              dmCadena020,
                Nombre              dmCadena256,
                Naturaleza          dmCadena001,
                Tercero             dmCadena001,
                Saldoinicial        dmMoneda,
                Debitos             dmMoneda,
                Creditos            dmMoneda,
                SaldoFinal          dmMoneda,
                ValorAbsoluto       dmCadena001,
                Subcuentas          dmEntero004
            )"""
        )
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")
        
        cursor.execute(f"create sequence GEN_{tabla}_ID")

        cursor.execute(f"""
            create trigger BI_{tabla}_ID for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_{tabla}_ID;
            end
        """)
        conexion.commit()

def Cuentas_cont(conexion, codigo, producto):
    if conexion:
        tabla = "Cuentas_Cont"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}(
                Id                  dmEntero004 not null,
                Codigo              dmCadena020,
                Nombre              dmCadena256,
                Naturaleza          dmCadena001,
                Tercero             dmCadena001,
                Saldoinicial        dmMoneda,
                Debitos             dmMoneda,
                Creditos            dmMoneda,
                SaldoFinal          dmMoneda,
                ValorAbsoluto       dmCadena001,
                Subcuentas          dmEntero004
            )"""
        )
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")

        cursor.execute(f"create sequence GEN_{tabla}_ID")

        cursor.execute(f"""
            create trigger BI_{tabla}_ID for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_{tabla}_ID;
            end
        """)
        conexion.commit()

def Terceros_mov_trib(conexion, codigo, producto):
    if conexion:
        tabla = "Terceros_mov_trib"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}(
                Id                  dmEntero004 not null,
                Identidad           dmCadena020,
                Cuenta              dmCadena020,
                Saldoinicial        dmMoneda,
                Debitos             dmMoneda,
                Creditos            dmMoneda,
                SaldoFinal          dmMoneda
            )"""
        )
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")
        
        cursor.execute(f"create sequence GEN_{tabla}_ID")

        cursor.execute(f"""
            create trigger BI_{tabla}_ID for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_{tabla}_ID;
            end
        """)

        conexion.commit()

def Terceros_mov_cont(conexion, codigo, producto):
    if conexion:
        tabla = "Terceros_mov_Cont"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}(
                Id                  dmEntero004 not null,
                Identidad           dmCadena020,
                Cuenta              dmCadena020,
                Saldoinicial        dmMoneda,
                Debitos             dmMoneda,
                Creditos            dmMoneda,
                SaldoFinal          dmMoneda
            )"""
        )
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")

        cursor.execute(f"create sequence GEN_{tabla}_ID")

        cursor.execute(f"""
            create trigger BI_{tabla}_ID for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_{tabla}_ID;
            end
        """)

        conexion.commit()

def Bancos_mov(conexion, codigo, producto):
    if conexion:
        tabla = "Bancos_mov"
        cursor = conexion.cursor()

        cursor.execute(f"""
            create table {tabla}(
                Identidad           dmCadena020 not null,
                Verificacion        dmCadena002,
                Nombre              dmCadena060,
                Saldo               dmMoneda
            )"""
        )
        conexion.commit()

def Cuentas_Atributos(conexion):
    """
    Crea la tabla relacional Cuentas_Atributos
    """
    tabla = "Cuentas_Atributos"
    if conexion:
        cursor = conexion.cursor()
        cursor.execute(f"""
            create table {tabla}
            (Id              dmEntero004 not null,
             IdCuenta        dmEntero004,
             IdAtributo      dmEntero004
            )
        """)
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")
        conexion.commit()

        cursor.execute("create sequence GEN_CUENTAS_ATRIBUTOS_ID")

        cursor.execute(f"""
            create trigger BI_CUENTAS_ATRIBUTOS for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_CUENTAS_ATRIBUTOS_ID;
            end
        """)
        conexion.commit()

def Hoja_trabajo(conexion):
    if conexion:
        tabla = "HOJA_TRABAJO"
        cursor = conexion.cursor()

        cursor.execute(f"""
            CREATE TABLE {tabla}(
                Id                  dmEntero008 not null,
                Idconcepto          dmEntero004,
                Idatributo          dmEntero004,
                Idelemento          dmEntero004,
                valor               dmCadena256,
                IdentidadTercero    dmCadena256
            )"""
        )
        cursor.execute(f"alter table {tabla} add constraint pk_{tabla} primary key (Id)")
        cursor.execute(f"grant select, insert, update, delete on table {tabla} to user HELISAADMON")
        conexion.commit()

        cursor.execute(f"create sequence GEN_{tabla}_ID")

        cursor.execute(f"""
            create trigger BI_{tabla} for {tabla}
            active before insert position 0
            as
            begin
              if (new.Id is null) then
                new.Id = next value for GEN_{tabla}_ID;
            end
        """)
        conexion.commit()

        # Tabla de undo para agrupar cuantías y numerar NITs extranjeros (por concepto)
        Hoja_trabajo_undo(conexion)


def Hoja_trabajo_undo(conexion):
    """Crea tabla de historial para deshacer agrupar cuantías menores y numerar NITs extranjeros."""
    tabla = "HOJA_TRABAJO_UNDO"
    if conexion:
        cursor = conexion.cursor()
        try:
            cursor.execute(f"""
                CREATE TABLE {tabla}(
                    Id              dmEntero008 NOT NULL,
                    TipoOp          dmEntero004 NOT NULL,
                    IdConcepto      dmEntero004 NOT NULL,
                    Payload         dmBlobText,
                    CreatedAt       dmFecha
                )
            """)
            cursor.execute(f"ALTER TABLE {tabla} ADD CONSTRAINT pk_{tabla} PRIMARY KEY (Id)")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tabla} TO USER HELISAADMON")
            conexion.commit()
        except Exception as e:
            conexion.rollback()
            if "already exists" not in str(e).lower() and "exists" not in str(e).lower():
                raise
        try:
            cursor.execute(f"CREATE SEQUENCE GEN_{tabla}_ID")
            conexion.commit()
        except Exception:
            conexion.rollback()
        try:
            cursor.execute(f"""
                CREATE TRIGGER BI_{tabla} FOR {tabla}
                ACTIVE BEFORE INSERT POSITION 0
                AS
                BEGIN
                  IF (new.Id IS NULL) THEN
                    new.Id = NEXT VALUE FOR GEN_{tabla}_ID;
                END
            """)
            conexion.commit()
        except Exception:
            conexion.rollback()
        cursor.close()

__all__ = [
    "Bancos_mov",
    "Consorcios",
    "Cuentas_Atributos",
    "Cuentas_cont",
    "Cuentas_trib",
    "Dominios",
    "Empresas",
    "Hoja_trabajo",
    "Hoja_trabajo_undo",
    "Terceros",
    "Terceros_mov_cont",
    "Terceros_mov_trib",
    "Usuarios",
]
