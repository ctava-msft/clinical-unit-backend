metadata description = 'Creates an Azure Cosmos DB for MongoDB account with a database.'
param accountName string
param databaseName string
param location string = resourceGroup().location
param tags object = {}

param collections array = []

resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2023-04-15' = {
  name: accountName
  location: location
  tags: tags
  kind: 'MongoDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    capabilities: [
      {
        name: 'EnableMongo'
      }
      {
        name: 'DisableRateLimitingResponses'
      }
    ]
    apiProperties: {
      serverVersion: '4.2'
    }
  }
}

resource database 'Microsoft.DocumentDB/databaseAccounts/mongodbDatabases@2023-04-15' = {
  name: databaseName
  parent: cosmosAccount
  properties: {
    resource: {
      id: databaseName
    }
  }
}

resource mongoCollections 'Microsoft.DocumentDB/databaseAccounts/mongodbDatabases/collections@2023-04-15' = [for collection in collections: {
  name: collection.name
  parent: database
  properties: {
    resource: {
      id: collection.id
      shardKey: {
        '${collection.shardKey}': 'Hash'
      }
    }
  }
}]

output accountId string = cosmosAccount.id
output accountName string = cosmosAccount.name
output databaseName string = databaseName
output endpoint string = cosmosAccount.properties.documentEndpoint
output host string = replace(replace(cosmosAccount.properties.documentEndpoint, 'https://', ''), ':443/', '')
