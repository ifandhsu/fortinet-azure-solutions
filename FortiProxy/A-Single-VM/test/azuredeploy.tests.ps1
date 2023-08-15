#Requires -Modules Pester
<#
.SYNOPSIS
    Tests a specific ARM template
.EXAMPLE
    Invoke-Pester
.NOTES
    This file has been created as an example of using Pester to evaluate ARM templates
#>

param (
    [string]$sshkey,
    [string]$sshkeypub
)
$VerbosePreference = "Continue"

BeforeAll {
    $templateName = "A-Single-VM"
    $sourcePath = "$env:GITHUB_WORKSPACE\FortiProxy\$templateName"
    $scriptPath = "$env:GITHUB_WORKSPACE\FortiProxy\$templateName\test"
    $templateFileName = "mainTemplate.json"
    $templateFileLocation = "$sourcePath\$templateFileName"
    $templateParameterFileName = "mainTemplate.parameters.json"
    $templateParameterFileLocation = "$sourcePath\$templateParameterFileName"

    # Basic Variables
    $testsRandom = Get-Random 10001
    $testsPrefix = "FORTIQA"
    $testsResourceGroupName = "FORTIQA-$testsRandom-$templateName"
    $testsAdminUsername = "azureuser"
    $testsResourceGroupLocation = "westeurope"

    # ARM Template Variables
    $publicIP1Name = "$testsPrefix-FPX-PIP"
    $params = @{ 'adminUsername'=$testsAdminUsername
                    'adminPassword'=$testsResourceGroupName
                    'fortiProxyNamePrefix'=$testsPrefix
                    'publicIP1Name'=$publicIP1Name
                }
    $ports = @(443, 22)
}

Describe 'FPX Single VM' {
    Context 'Validation' {
        It 'Has a JSON template' {
            $templateFileLocation | Should -Exist
        }

        It 'Has a parameters file' {
            $templateParameterFileLocation | Should -Exist
        }

        It 'Converts from JSON and has the expected properties' {
            $expectedProperties = '$schema',
            'contentVersion',
            'outputs',
            'parameters',
            'resources',
            'variables'
            $templateProperties = (get-content $templateFileLocation | ConvertFrom-Json -ErrorAction SilentlyContinue) | Get-Member -MemberType NoteProperty | % Name
            $templateProperties | Should -Be $expectedProperties
        }

        It 'Creates the expected Azure resources' {
            $expectedResources = 'Microsoft.Resources/deployments',
                                    'Microsoft.Compute/availabilitySets',
                                    'Microsoft.Network/virtualNetworks',
                                    'Microsoft.Network/networkSecurityGroups',
                                    'Microsoft.Network/publicIPAddresses',
                                    'Microsoft.Network/networkInterfaces',
                                    'Microsoft.Compute/virtualMachines'
            $templateResources = (get-content $templateFileLocation | ConvertFrom-Json -ErrorAction SilentlyContinue).Resources.type
            $templateResources | Should -Be $expectedResources
        }

        It 'Contains the expected parameters' {
            $expectedTemplateParameters = 'acceleratedNetworking',
                                            'adminPassword',
                                            'adminUsername',
                                            'availabilityOptions',
                                            'availabilityZoneNumber',
                                            'customImageReference',
                                            'existingAvailabilitySetName',
                                            'fortiManager',
                                            'fortiManagerIP',
                                            'fortiManagerSerial',
                                            'fortinetTags',
                                            'fortiProxyAdditionalCustomData',
                                            'fortiProxyImageSKU',
                                            'fortiProxyImageVersion',
                                            'fortiProxyLicenseBYOL',
                                            'fortiProxyName',
                                            'fortiProxyNamePrefix',
                                            'instanceType',
                                            'location',
                                            'publicIP1AddressType',
                                            'publicIP1Name',
                                            'publicIP1NewOrExistingOrNone',
                                            'publicIP1ResourceGroup',
                                            'publicIP1SKU',
                                            'serialConsole',
                                            'subnet1Name',
                                            'subnet1Prefix',
                                            'subnet1StartAddress',
                                            'vnetAddressPrefix',
                                            'vnetName',
                                            'vnetNewOrExisting',
                                            'vnetResourceGroup'
            $templateParameters = (get-content $templateFileLocation | ConvertFrom-Json -ErrorAction SilentlyContinue).Parameters | Get-Member -MemberType NoteProperty | % Name | Sort-Object
            $templateParameters | Should -Be $expectedTemplateParameters
        }

    }

    Context 'Deployment' {

        It "Test Deployment" {
            New-AzResourceGroup -Name $testsResourceGroupName -Location "$testsResourceGroupLocation"
            (Test-AzResourceGroupDeployment -ResourceGroupName "$testsResourceGroupName" -TemplateFile "$templateFileLocation" -TemplateParameterObject $params).Count | Should -Not -BeGreaterThan 0
        }
        It "Deployment" {
            Write-Host ( "Deployment name: $testsResourceGroupName" )

            $resultDeployment = New-AzResourceGroupDeployment -ResourceGroupName "$testsResourceGroupName" -TemplateFile "$templateFileLocation" -TemplateParameterObject $params
            Write-Host ($resultDeployment | Format-Table | Out-String)
            Write-Host ("Deployment state: " + $resultDeployment.ProvisioningState | Out-String)
            $resultDeployment.ProvisioningState | Should -Be "Succeeded"
        }
        It "Search deployment" {
            $result = Get-AzVM | Where-Object { $_.Name -like "$testsPrefix*" }
            Write-Host ($result | Format-Table | Out-String)
            $result | Should -Not -Be $null
        }
    }

    Context 'Deployment test' {

        BeforeAll {
            $FPX = (Get-AzPublicIpAddress -Name $publicIP1Name -ResourceGroupName $testsResourceGroupName).IpAddress
            Write-Host ("FortiProxy public IP: " + $FPX)
        }
        It "FPX: Ports listening" {
            ForEach( $port in $ports ) {
                Write-Host ("Check port: $port" )
                $portListening = (Test-Connection -TargetName $FPX -TCPPort $port -TimeoutSeconds 100)
                $portListening | Should -Be $true
            }
        }
    }

    Context 'Cleanup' {
        It "Cleanup of deployment" {
            Remove-AzResourceGroup -Name $testsResourceGroupName -Force
        }
    }
}
