param name string
param location string = resourceGroup().location
param sku object = {
  name: 'standard'
  family: 'A'
}
param principalId string = ''
param secretName string
@secure()
param secret string

resource keyVault 'Microsoft.KeyVault/vaults@2019-09-01' = {
  name: name
  location: location
  properties: {
    enabledForTemplateDeployment: true
    enabledForDeployment: true
    tenantId: tenant().tenantId
    enableRbacAuthorization: false
    sku: sku
    accessPolicies: [
      {
        objectId: principalId
        permissions: {
          secrets: [
            'all'
          ]
        }
        tenantId: tenant().tenantId
      }
    ]
  }
}

resource keyVaultSecret 'Microsoft.KeyVault/vaults/secrets@2019-09-01' = {
  parent: keyVault
  name: secretName
  properties: {
    value: secret
  }
}

output name string = keyVault.name
output secretName string = keyVaultSecret.name
