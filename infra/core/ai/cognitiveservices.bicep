metadata description = 'Creates an Azure Cognitive Services instance.'
param name string
param location string = resourceGroup().location
param tags object = {}
@description('The custom subdomain name used to access the API. Defaults to the value of the name parameter.')
param customSubDomainName string = name
param deployments array = []
param kind string = 'OpenAI'
param publicNetworkAccess string = 'Enabled'
param sku object = {
  name: 'S0'
}
param keyVaultProps object = {
  name:''
  secretName:''
  principalId:''
}

var saveKeysToVault = !empty(keyVaultProps.name) && !empty(keyVaultProps.secretName)

resource account 'Microsoft.CognitiveServices/accounts@2023-05-01' = {
  name: name
  location: location
  tags: tags
  kind: kind
  properties: {
    customSubDomainName: customSubDomainName
    publicNetworkAccess: publicNetworkAccess
  }
  sku: sku
}

@batchSize(1)
resource deployment 'Microsoft.CognitiveServices/accounts/deployments@2023-05-01' = [for deployment in deployments: {
  parent: account
  name: deployment.name
  properties: {
    model: deployment.model
    raiPolicyName: contains(deployment, 'raiPolicyName') ? deployment.raiPolicyName : null
  }
  sku: contains(deployment, 'sku') ? deployment.sku : {
    name: 'Standard'
    capacity: 20
  }
}]

module keyvault '../security/key-vault.bicep' = if (saveKeysToVault)  {
  name: 'keyvault'
  params: {
    name: keyVaultProps.name
    location: location
    secret: account.listKeys().key1
    secretName: keyVaultProps.secretName
    principalId: keyVaultProps.principalId
  }
}

module keyVaultRole '../security/role.bicep' = if (saveKeysToVault) {
  name: 'key-vault-role-backend'
  params: {
    principalId: keyVaultProps.principalId
    roleDefinitionId: '00482a5a-887f-4fb3-b363-3b7fe8e74483'
    principalType: 'User'
  }
}

output endpoint string = account.properties.endpoint
output id string = account.id
output name string = account.name

output keyVaultName string = saveKeysToVault ? keyvault.outputs.name : ''
output keyvaultSecretName string = saveKeysToVault ? keyvault.outputs.secretName : ''
