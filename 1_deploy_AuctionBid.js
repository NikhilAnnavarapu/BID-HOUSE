const bid=artifacts.require('AuctionBid')

module.exports=function(deployer){
    deployer.deploy(bid);
}