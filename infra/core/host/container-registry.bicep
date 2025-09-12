metadata description = 'Creates an Azure Container Registry.'
param name string
param location string = resourceGroup().location
param tags object = {}

@allowed([
  'Basic'
  'Standard'
  'Premium'
])
param sku string = 'Basic'

@allowed([
  'Enabled'
  'Disabled'
])
param adminUserEnabled string = 'Disabled'

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-01-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: adminUserEnabled == 'Enabled'
    publicNetworkAccess: publicNetworkAccess
  }
}

output id string = containerRegistry.id
output name string = containerRegistry.name
output loginServer string = containerRegistry.properties.loginServer
