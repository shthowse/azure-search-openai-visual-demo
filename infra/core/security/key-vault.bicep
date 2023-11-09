param name string
param location string = resourceGroup().location
param sku object = {
  name: 'standard'
  family: 'A'
}
param principalId string
param secretName string
param computerVisionId string
param applicationId string

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
      {
        objectId: applicationId
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
    value:  listKeys(computerVisionId, '2023-05-01').key1
  }
}

output name string = keyVault.name
output secretName string = keyVaultSecret.name
