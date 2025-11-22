// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AuctionBid {
    struct Item {
        string bidder;
        string owner;
        string item;
        string itemId;
        uint256 basePrice;
        uint256 currentPrice;
        uint256 timestamp;
    }

    // Array to store all items
    Item[] public items;
    mapping(string => Item) public itemMapping;
    
    function addItem(
        string memory _bidder,
        string memory _owner,
        string memory _item,
        string memory _itemId,
        uint256 _basePrice,
        uint256 _currentPrice
    ) public {
        require(bytes(_bidder).length > 0, "Bidder cannot be empty");
        require(bytes(_owner).length > 0, "Owner cannot be empty");
        require(bytes(_item).length > 0, "Item cannot be empty");
        require(bytes(_itemId).length > 0, "ItemId cannot be empty");
        require(_basePrice > 0, "Base price must be greater than 0");
        require(_currentPrice >= _basePrice, "Current price must be greater than or equal to base price");

        Item memory newItem = Item({
            bidder: _bidder,
            owner: _owner,
            item: _item,
            itemId: _itemId,
            basePrice: _basePrice,
            currentPrice: _currentPrice,
            timestamp: block.timestamp
        });

        items.push(newItem);
        itemMapping[_itemId] = newItem;
    }

    function placeBid(
        string memory _itemId,
        string memory _bidder,
        uint256 _newPrice
    ) public {
        require(bytes(_itemId).length > 0, "ItemId cannot be empty");
        require(bytes(_bidder).length > 0, "Bidder cannot be empty");
        require(_newPrice > 0, "Bid amount must be greater than 0");

        Item storage currentItem = itemMapping[_itemId];
        require(bytes(currentItem.itemId).length > 0, "Item not found");
        require(_newPrice > currentItem.currentPrice, "New bid must be higher than current price");

        // Update the item in mapping
        currentItem.currentPrice = _newPrice;
        currentItem.bidder = _bidder;
        currentItem.timestamp = block.timestamp;

        // Update the item in array
        for (uint i = 0; i < items.length; i++) {
            if (keccak256(bytes(items[i].itemId)) == keccak256(bytes(_itemId))) {
                items[i] = currentItem;
                break;
            }
        }
    }

    function getItemCount() public view returns (uint256) {
        return items.length;
    }

    function getItem(string memory _itemId) public view returns (
        string memory bidder,
        string memory owner,
        string memory item,
        string memory itemId,
        uint256 basePrice,
        uint256 currentPrice,
        uint256 timestamp
    ) {
        require(bytes(_itemId).length > 0, "ItemId cannot be empty");
        Item storage currentItem = itemMapping[_itemId];
        require(bytes(currentItem.itemId).length > 0, "Item not found");

        return (
            currentItem.bidder,
            currentItem.owner,
            currentItem.item,
            currentItem.itemId,
            currentItem.basePrice,
            currentItem.currentPrice,
            currentItem.timestamp
        );
    }

    function getItemsByBidder(string memory _bidder) public view returns (
        string[] memory itemIds,
        uint256[] memory prices
    ) {
        uint count = 0;
        for (uint i = 0; i < items.length; i++) {
            if (keccak256(bytes(items[i].bidder)) == keccak256(bytes(_bidder))) {
                count++;
            }
        }

        itemIds = new string[](count);
        prices = new uint256[](count);
        uint currentIndex = 0;

        for (uint i = 0; i < items.length; i++) {
            if (keccak256(bytes(items[i].bidder)) == keccak256(bytes(_bidder))) {
                itemIds[currentIndex] = items[i].itemId;
                prices[currentIndex] = items[i].currentPrice;
                currentIndex++;
            }
        }

        return (itemIds, prices);
    }
}
