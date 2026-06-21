// Azure AI Foundry + Azure Speech deployment
// Deploy with:
//   az deployment group create \
//     --resource-group <resourceGroupName> \
//     --template-file infra.bicep \
//     --parameters resourceGroupName=<rg> resourceName=<name> region=<region> [model=<model>]

targetScope = 'resourceGroup'

// ── Parameters ───────────────────────────────────────────────────────────────

@description('Name of the resource group being deployed into — applied as a tag on all resources.')
param resourceGroupName string

@description('Base name for all resources: Foundry hub, project, and Speech service. Max 15 chars.')
@minLength(3)
@maxLength(15)
param resourceName string

@description('Azure OpenAI model to deploy (e.g. gpt-4o, gpt-4o-mini). Leave empty to skip model deployment.')
param model string = ''

@description('Azure region for all resources (e.g. eastus, westeurope).')
param region string = resourceGroup().location

// ── Derived names ─────────────────────────────────────────────────────────────
// All names kept within Azure service character limits given @maxLength(15) above.

// Appending 'stg' guarantees ≥ 3 chars after stripping hyphens/underscores (satisfies BCP334).
var storageAccountName = take(toLower(replace(replace('${resourceName}stg', '-', ''), '_', '')), 24)
var keyVaultName       = '${resourceName}-kv'       // max 17 — within KV 24-char limit
var aiServicesName     = '${resourceName}-ai'       // max 18 — CogSvc 64-char limit
var speechServiceName  = '${resourceName}-speech'   // max 22 — CogSvc 64-char limit
var hubName            = '${resourceName}-hub'      // max 19
var projectName        = '${resourceName}-project'  // max 23

var commonTags = {
  project: 'ai-podcast-workshop'
  resourceGroup: resourceGroupName
}

// ── Storage Account (AI Hub dependency) ──────────────────────────────────────

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  // resourceName @minLength(3) + 'stg' suffix guarantees ≥ 6 chars; replace() only removes chars
  // not in 'stg', so the suffix is always preserved — BCP334 is a false positive here.
  #disable-next-line BCP334
  name: storageAccountName
  location: region
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  tags: commonTags
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
  }
}

// ── Key Vault (AI Hub dependency) ────────────────────────────────────────────

resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: keyVaultName
  location: region
  tags: commonTags
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenant().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
    softDeleteRetentionInDays: 7
  }
}

// ── Azure AI Services (Foundry model endpoint + API key) ─────────────────────

resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: aiServicesName
  location: region
  kind: 'AIServices'
  sku: { name: 'S0' }
  tags: commonTags
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: aiServicesName
  }
}

// Optional — only deployed when a model name is provided.
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = if (!empty(model)) {
  parent: aiServices
  name: empty(model) ? 'none' : model
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-5.4-nano'
    }
    scaleSettings: {
      scaleType: 'Standard'
    }
  }
}

// ── AI Foundry Hub ───────────────────────────────────────────────────────────

resource aiHub 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: hubName
  location: region
  identity: { type: 'SystemAssigned' }
  kind: 'Hub'
  tags: commonTags
  properties: {
    friendlyName: hubName
    storageAccount: storageAccount.id
    keyVault: keyVault.id
  }
}

// Wire AI Services into the hub so its models are available to all projects.
resource aiServicesHubConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = {
  parent: aiHub
  name: '${aiServicesName}-connection'
  properties: {
    category: 'AIServices'
    target: aiServices.properties.endpoint
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: aiServices.listKeys().key1
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: aiServices.id
    }
  }
}

// ── AI Foundry Project ───────────────────────────────────────────────────────

resource aiProject 'Microsoft.MachineLearningServices/workspaces@2024-10-01' = {
  name: projectName
  location: region
  identity: { type: 'SystemAssigned' }
  kind: 'Project'
  tags: commonTags
  properties: {
    friendlyName: projectName
    hubResourceId: aiHub.id
  }
}

// ── Azure Speech Service (MAI-2 TTS via https://<region>.tts.speech.microsoft.com/) ──

resource speechService 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: speechServiceName
  location: region
  kind: 'SpeechServices'
  sku: { name: 'S0' }  // S0 required for neural voices including MAI-2
  tags: commonTags
  properties: {
    publicNetworkAccess: 'Enabled'
    customSubDomainName: speechServiceName
  }
}

// Link Speech Service to the Foundry project so it is discoverable from the project.
resource speechProjectConnection 'Microsoft.MachineLearningServices/workspaces/connections@2024-10-01' = {
  parent: aiProject
  name: '${speechServiceName}-connection'
  properties: {
    category: 'CognitiveService'
    target: speechService.properties.endpoint
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: speechService.listKeys().key1
    }
    metadata: {
      ResourceId: speechService.id
    }
  }
}

// ── Outputs ──────────────────────────────────────────────────────────────────

@description('Azure AI Foundry project endpoint → FOUNDRY_PROJECT_ENDPOINT')
output foundryProjectEndpoint string = aiServices.properties.endpoint

@description('Azure AI Foundry API key → FOUNDRY_API_KEY')
// Keys are intentional outputs — suppressing linter warnings.
#disable-next-line outputs-should-not-contain-secrets
output foundryProjectKey string = aiServices.listKeys().key1

@description('MAI-2 TTS regional endpoint → MAI_VOICE_2_ENDPOINT')
output maiVoice2Endpoint string = 'https://${region}.tts.speech.microsoft.com/'

@description('Azure Speech Service key → MAI_VOICE_2_KEY')
#disable-next-line outputs-should-not-contain-secrets
output maiVoice2Key string = speechService.listKeys().key1
