Entendido. Simplificaremos aún más el script para dejarlo exclusivamente como la base fundacional de datos: tu Data Lake en **S3** y tu base de datos vectorial (ChromaDB) en **EC2**.

Al eliminar Cloud9, el script es mucho más rápido de ejecutar y dejamos la arquitectura lo más limpia y económica posible.

Aquí tienes la versión ajustada:

### Script Actualizado (`setup_aws.sh`)

```bash
#!/bin/bash
# ==========================================
# AUTOMATIZACIÓN DE INFRAESTRUCTURA - SGA
# Archivo: scripts/setup_aws.sh
# (Versión Minimalista: S3 Data Lake + EC2 ChromaDB)
# ==========================================

# Detener el script si ocurre algún error en comandos críticos
set -e

# Variables globales para limpieza y seguimiento
CREATED_RESOURCES=()
BUCKET_NAME=""
INSTANCE_ID=""
EC2_SG_ID=""

# ---------------------------------------------------------
# FUNCIÓN: VALIDACIONES Y PRERREQUISITOS
# ---------------------------------------------------------
validate_prerequisites() {
    echo " Validando prerrequisitos..."
    
    if ! command -v aws &> /dev/null; then
        echo " Error: AWS CLI no está instalado"
        exit 1
    fi
    
    if ! aws sts get-caller-identity &> /dev/null; then
        echo " Error: Credenciales AWS no configuradas. Ejecuta: aws configure"
        exit 1
    fi
    
    echo "Prerrequisitos validados correctamente"
}

# ---------------------------------------------------------
# FUNCIÓN: VERIFICAR SI RECURSOS YA EXISTEN
# ---------------------------------------------------------
check_existing_resources() {
    echo " Verificando recursos existentes..."
    
    if aws s3 ls "s3://$BUCKET_NAME" &> /dev/null; then
        echo "  El bucket $BUCKET_NAME ya existe"
        read -p "¿Deseas continuar usando el bucket existente? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "❌ Operación cancelada"
            exit 1
        fi
        BUCKET_EXISTS=true
    else
        BUCKET_EXISTS=false
    fi
}

# ---------------------------------------------------------
# FUNCIÓN: LIMPIEZA EN CASO DE ERROR
# ---------------------------------------------------------
cleanup_on_error() {
    echo ""
    echo " Error detectado. Iniciando limpieza de recursos..."
    
    if [[ -n "$INSTANCE_ID" ]]; then
        echo "   Terminando instancia EC2 (Chroma)..."
        aws ec2 terminate-instances --instance-ids $INSTANCE_ID 2>/dev/null || true
    fi
    
    if [[ -n "$EC2_SG_ID" ]]; then
        echo "   Eliminando Security Group: $EC2_SG_ID..."
        aws ec2 delete-security-group --group-id $EC2_SG_ID 2>/dev/null || true
    fi
    
    if [[ -n "$BUCKET_NAME" && "$BUCKET_EXISTS" != "true" ]]; then
        echo "   Eliminando bucket S3..."
        aws s3 rb s3://$BUCKET_NAME --force 2>/dev/null || true
    fi
    
    echo "🧹 Limpieza completada por error"
    exit 1
}

trap cleanup_on_error ERR

# ---------------------------------------------------------
# FUNCIÓN: CREAR SCRIPT DE LIMPIEZA MANUAL
# ---------------------------------------------------------
create_cleanup_script() {
    cat > "cleanup-sga-$PROJECT_ID.sh" << EOF
#!/bin/bash
# Script de limpieza para recursos SGA - Project ID: $PROJECT_ID

echo " Iniciando limpieza de recursos SGA..."

if [[ -n "$INSTANCE_ID" ]]; then
    echo "Terminando instancia EC2 (Chroma)..."
    aws ec2 terminate-instances --instance-ids $INSTANCE_ID
    aws ec2 wait instance-terminated --instance-ids $INSTANCE_ID
fi

if [[ -n "$EC2_SG_ID" ]]; then
    echo "Eliminando Security Group EC2..."
    aws ec2 delete-security-group --group-id $EC2_SG_ID
fi

read -p "¿Deseas eliminar el bucket S3 $BUCKET_NAME y todos sus datos? (y/N): " -n 1 -r
echo
if [[ \$REPLY =~ ^[Yy]$ ]]; then
    echo "Eliminando bucket S3..."
    aws s3 rb s3://$BUCKET_NAME --force
fi

echo "Limpieza completada"
EOF
    chmod +x "cleanup-sga-$PROJECT_ID.sh"
}

# ---------------------------------------------------------
# INICIO DEL SCRIPT PRINCIPAL
# ---------------------------------------------------------
validate_prerequisites

PROJECT_ID=$RANDOM
BUCKET_NAME="sga-data-lake-$PROJECT_ID"
REGION=$(aws configure get region)
REGION=${REGION:-us-east-1}

echo "======================================================="
echo " INICIANDO DESPLIEGUE AWS - PLATAFORMA SGA"
echo " Región objetivo: $REGION | ID de Proyecto: $PROJECT_ID"
echo "======================================================="

check_existing_resources

# ---------------------------------------------------------
# FASE 0: OBTENER REDES (VPC)
# ---------------------------------------------------------
echo -e "\n [1/4] Obteniendo configuración de Red (VPC)..."
VPC_ID=$(aws ec2 describe-vpcs --filters "Name=isDefault,Values=true" --query "Vpcs[0].VpcId" --output text)

if [[ "$VPC_ID" == "None" || -z "$VPC_ID" ]]; then
    echo "Error: No se encontró VPC default"
    exit 1
fi
echo " VPC Default: $VPC_ID"

# ---------------------------------------------------------
# FASE 1: DATA LAKE (S3)
# ---------------------------------------------------------
echo -e "\n [2/4] Configurando Data Lake S3..."
if [[ "$BUCKET_EXISTS" == "true" ]]; then
    echo " Usando bucket existente: $BUCKET_NAME"
else
    aws s3 mb s3://$BUCKET_NAME --region $REGION
    for folder in "quarantine/" "bronce/" "silver/" "gold/"; do
        aws s3api put-object --bucket $BUCKET_NAME --key "$folder" > /dev/null
    done
    echo " Bucket y estructura Medallón creados exitosamente"
fi

# ---------------------------------------------------------
# FASE 2: GRUPO DE SEGURIDAD EC2 (CHROMA)
# ---------------------------------------------------------
echo -e "\n️ [3/4] Configurando Security Group para EC2 (ChromaDB)..."

EC2_SG_ID=$(aws ec2 create-security-group \
    --group-name "sga-ec2-sg-$PROJECT_ID" \
    --description "SGA EC2 SG Chroma - Project $PROJECT_ID" \
    --vpc-id $VPC_ID \
    --tag-specifications 'ResourceType=security-group,Tags=[{Key=Name,Value=SGA-EC2-SG},{Key=Project,Value=SGA}]' \
    --query 'GroupId' --output text)

# Habilitar SOLO SSH (22) y ChromaDB (4000)
aws ec2 authorize-security-group-ingress --group-id $EC2_SG_ID --protocol tcp --port 22 --cidr 0.0.0.0/0 > /dev/null
aws ec2 authorize-security-group-ingress --group-id $EC2_SG_ID --protocol tcp --port 4000 --cidr 0.0.0.0/0 > /dev/null

echo " EC2 Security Group creado: $EC2_SG_ID (Puertos: 22, 4000)"

# ---------------------------------------------------------
# FASE 3: SERVIDOR EC2 (CHROMA)
# ---------------------------------------------------------
echo -e "\n️ [4/4] Desplegando Servidor EC2 (ChromaDB)..."

AMI_ID=$(aws ssm get-parameters --names /aws/service/canonical/ubuntu/server/22.04/stable/current/amd64/hvm/ebs-gp2/ami-id --query 'Parameters[0].Value' --output text)

INSTANCE_ID=$(aws ec2 run-instances \
    --image-id $AMI_ID \
    --instance-type t3.medium \
    --key-name vockey \
    --security-group-ids $EC2_SG_ID \
    --associate-public-ip-address \
    --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=SGA-EC2-Chroma-$PROJECT_ID},{Key=Project,Value=SGA}]" \
    --query 'Instances[0].InstanceId' \
    --output text)

echo " Instancia EC2 creada: $INSTANCE_ID"
aws ec2 wait instance-running --instance-ids $INSTANCE_ID
EC2_PUBLIC_IP=$(aws ec2 describe-instances --instance-ids $INSTANCE_ID --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
echo " IP Pública de EC2 (Chroma): $EC2_PUBLIC_IP"

# ---------------------------------------------------------
# CREAR ARCHIVOS DE CONFIGURACIÓN
# ---------------------------------------------------------
echo -e "\n Creando archivos de configuración..."

cat > "sga-config-$PROJECT_ID.env" << EOF
# Configuración SGA - $(date)
PROJECT_ID=$PROJECT_ID
REGION=$REGION

# Infraestructura S3
S3_BUCKET_NAME=$BUCKET_NAME

# EC2 (ChromaDB)
EC2_INSTANCE_ID=$INSTANCE_ID
EC2_SG_ID=$EC2_SG_ID
EC2_PUBLIC_IP=$EC2_PUBLIC_IP
CHROMADB_URL=http://$EC2_PUBLIC_IP:4000
EOF

create_cleanup_script
trap - ERR

# ---------------------------------------------------------
# RESUMEN FINAL
# ---------------------------------------------------------
echo -e "\n======================================================="
echo " DESPLIEGUE FINALIZADO CON ÉXITO!"
echo "======================================================="
echo " INFRAESTRUCTURA CREADA:"
echo "   - Bucket S3:  $BUCKET_NAME"
echo "   - EC2 ID:     $INSTANCE_ID"
echo ""
echo " URL DE ACCESO EC2 (Vector DB):"
echo "   ChromaDB:     http://$EC2_PUBLIC_IP:4000"
echo "   SSH Access:   ssh -i vockey.pem ubuntu@$EC2_PUBLIC_IP"
echo "======================================================="

```