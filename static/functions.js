const roleSelect = document.getElementById("selection-dropdown");
roleSelect.addEventListener('change', handleSelection)



function handleSelection(value){
    const curVal = value.target.value;
    console.log(curVal);
    const bidForm = document.getElementById("bidder-cc-info")
    const sellerForm = document.getElementById("seller-bank-info")
    const hdForm = document.getElementById("helpdesk-position-info")
    // Bidder Credit card form info
    const ccnum = document.getElementById("ccnum")
    const cctype = document.getElementById("cctype")
    const expmonth = document.getElementById("expmonth")
    const cvvnum = document.getElementById("cvvnum")
    const owneremail = document.getElementById("owneremail")
    //Seller bank info
    const routingnum = document.getElementById("routingnum")
    const accnum = document.getElementById("accnum")
    const balance = document.getElementById("balance")
    //Helpdesk position info
    const position = document.getElementById("position")
    //age and major info section
    const ageAndMajor = document.getElementById("age-major-info")
    const age = document.getElementById("age")
    const major = document.getElementById("major")
    //address information
    const addrInfo = document.getElementById("address-info")
    const zipcode = document.getElementById("zip")
    const stNum = document.getElementById("stnum")
    const stName = document.getElementById("stname")



    if (curVal == "bidder"){
        bidForm.hidden = false
        sellerForm.hidden = true
        hdForm.hidden = true
        ageAndMajor.hidden = false
        addrInfo.hidden = false

        ccnum.required = true
        cctype.required = true
        expmonth.required = true
        cvvnum.required = true
        owneremail.required = true
        age.required = true
        major.required = true
        zipcode.required = true
        stNum.required = true
        stName.required = true

        position.required = false
        position.value = ""
        routingnum.required = false
        routingnum.value = " "
        accnum.required = false
        accnum.value = " "
        balance.required = false
        balance.value = " "

    }
    if (curVal == "seller"){
        bidForm.hidden = true
        sellerForm.hidden = false
        hdForm.hidden = true
        ageAndMajor.hidden = false
        addrInfo.hidden = false

        routingnum.required = true
        accnum.required = true
        balance.required = true
        age.required = true
        major.required = true
        zipcode.required = true
        stNum.required = true
        stName.required = true

        ccnum.required = false
        cctype.required = false
        expmonth.required = false
        cvvnum.required = false
        owneremail.required = false
        age.required = false
        major.required = false
        zipcode.required = false
        stNum.required = false
        stName.required = false
        position.required = false

        ccnum.value = " "
        cctype.value = " "
        expmonth.value = " "
        cvvnum.value = " "
        owneremail.value = " "
        position.value = " "
    }
    if (curVal == "helpdesk"){
        bidForm.hidden = true
        sellerForm.hidden = true
        hdForm.hidden = false
        position.required = true
        ageAndMajor.hidden = true
        addrInfo.hidden = true

        ccnum.required = false
        cctype.required = false
        expmonth.required = false
        cvvnum.required = false
        owneremail.required = false
        age.required = false
        major.required = false
        zipcode.required = false
        stNum.required = false
        stName.required = false
        routingnum.required = false
        accnum.required = false
        balance.required = false

        ccnum.value = " "
        cctype.value = " "
        expmonth.value = " "
        cvvnum.value = " "
        owneremail.value = " "
        age.value = " "
        major.value = " "
        zipcode.value = " "
        stNum.value = " "
        stName.value = " "
        routingnum.value = " "
        accnum.value = " "
        balance.value = " "
    }

}

const ccNumber = document.getElementById("ccnum")
console.log(ccNumber)
ccNumber.addEventListener('blur', hyphenate())
function hyphenate(ccNumber){
    return ccNumber.value = ccNumber.value.slice(0,4)+ "-"+ccNumber.value.slice(4,8)+ "-" + ccNumber.value.slice(8,12)+ "-"+ccNumber.value.slice(12,16)
}



function confirmPwd(){
    let pwd = document.getElementById("password")
    let cpwd = document.getElementById("confirmpassword")
    let matchingText = document.getElementById("matching-text")
    if(cpwd.value){
        if(pwd.value != cpwd.value){
            matchingText.style.display = 'block'
            matchingText.style.color = 'red'
            matchingText.innerHTML = ' The passwords do not match not Matching'
            matchingText.hidden = false
            return false
            e.preventDefault()


        }
        else{
            matchingText.style.display = 'block'
            matchingText.style.color = 'green'
            matchingText.innerHTML = 'Matching'
        }
    }
    else{
        matchingText.innerHTML = 'none'
    }
}

function checkBid(){
    let bidAmt = document.getElementById("bid")
    let curBid = document.getElementById("current_bid")
    let priceText = document.getElementById("price-text")

    if(bidAmt.value <= parseInt(curBid.innerText)){
        priceText.style.display = 'block'
        priceText.style.color = 'red'
        priceText.hidden = false
        return false
        e.preventDefault()
    }

}

function endListing(){
    let endMsg = document.getElementById("end-msg")
    endMsg.hidden = false
}

