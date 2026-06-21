#!/usr/bin/env bash
# deploy.sh — Provision Azure AI Foundry + Azure Speech resources
# Usage: bash deploy.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BICEP_FILE="${SCRIPT_DIR}/infra.bicep"

# ── Pre-flight checks ─────────────────────────────────────────────────────────
[[ -f "$BICEP_FILE" ]] \
  || { echo "ERROR: infra.bicep not found at ${BICEP_FILE}"; exit 1; }
command -v az &>/dev/null \
  || { echo "ERROR: Azure CLI not installed — see https://aka.ms/installazurecli"; exit 1; }
command -v jq &>/dev/null \
  || { echo "ERROR: jq is required — apt install jq  or  brew install jq"; exit 1; }

# ── Colour helpers ────────────────────────────────────────────────────────────
R='\033[0;31m' G='\033[0;32m' Y='\033[1;33m' B='\033[0;34m' BD='\033[1m' DM='\033[2m' N='\033[0m'

hr()   { printf "\n${B}%s${N}\n\n" "$(printf '─%.0s' {1..60})"; }
h()    { printf "  ${BD}%s${N}\n" "$*"; }
info() { printf "  ${B}→${N}  %s\n" "$*"; }
ok()   { printf "  ${G}✓${N}  %s\n" "$*"; }
warn() { printf "  ${Y}!${N}  %s\n" "$*"; }
die()  { printf "\n  ${R}✗${N}  %s\n\n" "$*" >&2; exit 1; }

ask() {
  # Usage: ask "Prompt text" VARNAME [default]
  local prompt="$1" varname="$2" default="${3:-}" input
  [[ -n "$default" ]] \
    && printf "  %s ${DM}[%s]${N}: " "$prompt" "$default" \
    || printf "  %s: " "$prompt"
  read -r input
  printf -v "$varname" '%s' "${input:-$default}"
}

# ── Random 10-char suffix for default names ───────────────────────────────────
SUFFIX=$(openssl rand -hex 5)   # 10 lowercase hex chars

# ── 1. Azure CLI login ────────────────────────────────────────────────────────
hr
h "Azure Login"
echo ""

if ! az account show &>/dev/null; then
  warn "Not logged in — starting browser login..."
  az login --output none
fi
ok "Logged in as $(az account show --query user.name -o tsv)"

# ── 2. Subscription selection ─────────────────────────────────────────────────
hr
h "Select Subscription"
echo ""

SUBS_JSON=$(az account list --output json | jq 'sort_by(.name)')
mapfile -t SUB_NAMES   < <(echo "$SUBS_JSON" | jq -r '.[].name')
mapfile -t SUB_IDS     < <(echo "$SUBS_JSON" | jq -r '.[].id')
mapfile -t SUB_ACTIVE  < <(echo "$SUBS_JSON" | jq -r '.[].isDefault')

DEFAULT_IDX=1
for i in "${!SUB_ACTIVE[@]}"; do
  [[ "${SUB_ACTIVE[$i]}" == "true" ]] && DEFAULT_IDX=$(( i + 1 )) && break
done

for i in "${!SUB_NAMES[@]}"; do
  MARKER=""
  [[ "${SUB_ACTIVE[$i]}" == "true" ]] && MARKER=" ${G}← active${N}"
  printf "  %2d)  %-40s  ${DM}%s${N}%b\n" \
    $(( i + 1 )) "${SUB_NAMES[$i]}" "${SUB_IDS[$i]}" "$MARKER"
done
echo ""

ask "Enter number" SUB_CHOICE "$DEFAULT_IDX"

[[ "$SUB_CHOICE" =~ ^[0-9]+$ ]] \
  && (( SUB_CHOICE >= 1 && SUB_CHOICE <= ${#SUB_IDS[@]} )) \
  || die "Invalid selection: ${SUB_CHOICE}"

SUBSCRIPTION_ID="${SUB_IDS[$(( SUB_CHOICE - 1 ))]}"
SUBSCRIPTION_NAME="${SUB_NAMES[$(( SUB_CHOICE - 1 ))]}"

az account set --subscription "$SUBSCRIPTION_ID" --output none
ok "Using: ${SUBSCRIPTION_NAME}  ${DM}(${SUBSCRIPTION_ID})${N}"

# ── 3–6. Deployment parameters ────────────────────────────────────────────────
hr
h "Deployment Parameters"
echo ""

# Resource name max is 15 chars (Bicep constraint). Default is "aipw-<suffix>" = exactly 15.
DEFAULT_RG="ai-podcast-workshop-${SUFFIX}"
DEFAULT_NAME="aipw-${SUFFIX}"

ask "Resource group name"              RESOURCE_GROUP  "$DEFAULT_RG"
ask "Resource name (max 15)"          RESOURCE_NAME   "$DEFAULT_NAME"
ask "Azure region"                    REGION          "eastus"
ask "Model to deploy (enter to skip)" MODEL           "gpt-5.4-nano"

(( ${#RESOURCE_NAME} <= 15 )) \
  || die "Resource name '${RESOURCE_NAME}' is ${#RESOURCE_NAME} chars — max allowed is 15"

MODEL_DISPLAY="${MODEL:-${DM}(none — skipping model deployment)${N}}"
echo ""
printf "  ${DM}%-22s  %s${N}\n" "Subscription:"  "$SUBSCRIPTION_NAME"
printf "  ${DM}%-22s  %s${N}\n" "Resource group:" "$RESOURCE_GROUP"
printf "  ${DM}%-22s  %s${N}\n" "Resource name:"  "$RESOURCE_NAME"
printf "  ${DM}%-22s  %s${N}\n" "Region:"         "$REGION"
printf "  %-22s  %b\n"          "Model:"          "$MODEL_DISPLAY"
echo ""

read -rp "  Proceed? [Y/n]: " CONFIRM
[[ "${CONFIRM:-Y}" =~ ^[Nn] ]] && { echo ""; echo "  Aborted."; echo ""; exit 0; }

# ── Create resource group if needed ───────────────────────────────────────────
hr
h "Resource Group"
echo ""

if az group show --name "$RESOURCE_GROUP" &>/dev/null; then
  ok "'${RESOURCE_GROUP}' already exists"
else
  info "Creating '${RESOURCE_GROUP}' in '${REGION}'..."
  az group create --name "$RESOURCE_GROUP" --location "$REGION" --output none
  ok "Created"
fi

# ── Submit deployment ─────────────────────────────────────────────────────────
hr
h "Deploying"
echo ""

DEPLOYMENT_NAME="infra-$(date +%Y%m%d%H%M%S)"
PORTAL_RG_URL="https://portal.azure.com/#resource/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/overview"
PORTAL_DEPLOYS_URL="https://portal.azure.com/#resource/subscriptions/${SUBSCRIPTION_ID}/resourceGroups/${RESOURCE_GROUP}/deployments"

# Build params array — only include model when provided.
DEPLOY_PARAMS=(
  "resourceGroupName=${RESOURCE_GROUP}"
  "resourceName=${RESOURCE_NAME}"
  "region=${REGION}"
)
[[ -n "$MODEL" ]] && DEPLOY_PARAMS+=("model=${MODEL}")

az deployment group create \
  --resource-group "$RESOURCE_GROUP" \
  --template-file  "$BICEP_FILE" \
  --name           "$DEPLOYMENT_NAME" \
  --parameters     "${DEPLOY_PARAMS[@]}" \
  --no-wait \
  --output none

info "Submitted — polling every 10s  ${DM}(this typically takes 5–10 minutes)${N}"
echo ""

# ── Poll for completion ───────────────────────────────────────────────────────
START_TS=$(date +%s)
LAST_STATE=""

get_state() {
  az deployment group show \
    --resource-group "$RESOURCE_GROUP" \
    --name "$DEPLOYMENT_NAME" \
    --query properties.provisioningState \
    -o tsv 2>/dev/null || echo "Pending"
}

while true; do
  STATE=$(get_state)
  ELAPSED=$(( $(date +%s) - START_TS ))
  ELAPSED_FMT=$(printf "%dm%02ds" $(( ELAPSED / 60 )) $(( ELAPSED % 60 )))

  if [[ "$STATE" != "$LAST_STATE" ]]; then
    # Clear any in-progress \r line, then print state transition
    printf "\r%-60s\n" ""
    printf "  ${DM}[%s]${N} %s\n" "$ELAPSED_FMT" "$STATE"
    LAST_STATE="$STATE"
  else
    printf "\r  ${DM}[%s] %s …${N}  " "$ELAPSED_FMT" "$STATE"
  fi

  case "$STATE" in
    Succeeded)
      printf "\n"
      break
      ;;
    Failed|Canceled)
      printf "\n\n  ${R}✗  Deployment ${STATE,,}${N}\n\n"

      ERR_JSON=$(az deployment group show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DEPLOYMENT_NAME" \
        --query "properties.error" \
        -o json 2>/dev/null || echo "null")

      if [[ "$ERR_JSON" != "null" && -n "$ERR_JSON" ]]; then
        echo "$ERR_JSON" \
          | jq -r '.. | .message? // empty' 2>/dev/null \
          | grep -v '^$' \
          | head -8 \
          | while IFS= read -r msg; do
              printf "  ${R}│${N} %s\n" "$msg"
            done
        echo ""
      fi

      warn "To clean up the failed deployment, visit:"
      printf "  ${B}%s${N}\n\n" "$PORTAL_DEPLOYS_URL"
      exit 1
      ;;
  esac

  sleep 10
done

# ── Collect outputs ───────────────────────────────────────────────────────────
OUTPUTS=$(az deployment group show \
  --resource-group "$RESOURCE_GROUP" \
  --name           "$DEPLOYMENT_NAME" \
  --query properties.outputs \
  -o json)

FOUNDRY_ENDPOINT=$(echo "$OUTPUTS" | jq -r '.foundryProjectEndpoint.value // empty')
FOUNDRY_KEY=$(echo "$OUTPUTS"      | jq -r '.foundryProjectKey.value      // empty')
MAI_ENDPOINT=$(echo "$OUTPUTS"     | jq -r '.maiVoice2Endpoint.value      // empty')
MAI_KEY=$(echo "$OUTPUTS"          | jq -r '.maiVoice2Key.value            // empty')

# ── Done ──────────────────────────────────────────────────────────────────────
hr
h "Done  ${G}✓${N}"
echo ""
ok "All resources provisioned in ${ELAPSED_FMT}"
echo ""
info "Resource group:"
printf "  ${B}%s${N}\n" "$PORTAL_RG_URL"
echo ""
info "Add these to your .env:"
echo ""
printf "  MODEL_PROVIDER=foundry\n"
printf "  FOUNDRY_PROJECT_ENDPOINT=%s\n" "$FOUNDRY_ENDPOINT"
printf "  FOUNDRY_MODEL=%s\n"            "$MODEL"
printf "  FOUNDRY_API_KEY=%s\n"          "$FOUNDRY_KEY"
printf "  MAI_VOICE_2_ENDPOINT=%s\n"     "$MAI_ENDPOINT"
printf "  MAI_VOICE_2_KEY=%s\n"          "$MAI_KEY"
echo ""
